"""
DataLoader：题材包加载与 schema 校验

Phase 3 题材包加载入口，从独立目录加载 theme.yaml + chapters/ + npcs/ + config.yaml，
并对关键字段做 schema 校验，缺失字段给出明确错误。

主题包结构：
    theme_mars_base/
        theme.yaml         # 题材元信息
        config.yaml        # 资源/状态字段/结局/命令定义
        data/
            chapters/*.yaml
            branches/*.yaml
            npcs/*.yaml
        templates/         # （可选）人格模板覆盖

作者：锐锋-核心开发工程师  日期：2026-08-09
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ThemeBundle:
    """题材包加载结果"""
    theme_id: str = ""
    theme_name: str = ""
    engine_version: str = ""
    theme_dir: str = ""
    manifest: Dict[str, Any] = field(default_factory=dict)   # theme.yaml 全文
    config: Dict[str, Any] = field(default_factory=dict)     # config.yaml 全文
    chapters_dir: str = ""
    branches_dir: str = ""
    npcs_dir: str = ""
    templates_dir: str = ""
    errors: List[str] = field(default_factory=list)          # schema 校验错误


class DataLoader:
    """题材包加载器

    用法：
        loader = DataLoader()
        bundle = loader.load_theme("/path/to/theme_mars_base")
        if bundle.errors:
            for e in bundle.errors: print(e)
    """

    # theme.yaml 必填字段
    REQUIRED_THEME_FIELDS = ["theme_id", "theme_name"]

    # config.yaml 可选子节
    OPTIONAL_CONFIG_SECTIONS = [
        "state_schema", "resources", "endings", "commands",
    ]

    def load_theme(self, theme_dir: str) -> Optional[ThemeBundle]:
        """加载题材包

        Args:
            theme_dir: 题材包根目录路径

        Returns:
            ThemeBundle 实例（含 errors 字段），或 None（目录不存在）
        """
        if not os.path.isdir(theme_dir):
            logger.error(f"题材包目录不存在: {theme_dir}")
            return None

        bundle = ThemeBundle(theme_dir=theme_dir)

        # 1. 加载 theme.yaml
        manifest = self._load_yaml(os.path.join(theme_dir, "theme.yaml"))
        if manifest is None:
            bundle.errors.append("theme.yaml 缺失或解析失败")
            return bundle
        bundle.manifest = manifest

        # schema 校验：必填字段
        for f in self.REQUIRED_THEME_FIELDS:
            if not manifest.get(f):
                bundle.errors.append(f"theme.yaml 缺失必填字段: {f}")

        bundle.theme_id = manifest.get("theme_id", "")
        bundle.theme_name = manifest.get("theme_name", "")
        bundle.engine_version = manifest.get("engine_version", "")

        # 2. 解析子目录路径（支持相对路径，相对于 theme_dir）
        data_root = manifest.get("data_root", "data")
        if not os.path.isabs(data_root):
            data_root = os.path.join(theme_dir, data_root)

        bundle.chapters_dir = self._resolve_subdir(manifest, "chapters_dir", "chapters", data_root, theme_dir)
        bundle.branches_dir = self._resolve_subdir(manifest, "branches_dir", "branches", data_root, theme_dir)
        bundle.npcs_dir = self._resolve_subdir(manifest, "npcs_dir", "npcs", data_root, theme_dir)
        bundle.templates_dir = self._resolve_subdir(manifest, "templates_dir", "templates", "", theme_dir)

        # 3. 加载 config.yaml（可选）
        config_path = manifest.get("config_path", "config.yaml")
        if not os.path.isabs(config_path):
            config_path = os.path.join(theme_dir, config_path)
        config = self._load_yaml(config_path)
        if config is None:
            logger.debug(f"题材包 {bundle.theme_id} 无 config.yaml（可选）")
            config = {}
        bundle.config = config

        # schema 校验：config.yaml 子节
        # state_schema 是 dict（含 fields 列表）；其余 section 应为列表
        for section in self.OPTIONAL_CONFIG_SECTIONS:
            if section not in config:
                continue
            if section == "state_schema":
                if not isinstance(config[section], dict):
                    bundle.errors.append(f"config.yaml 子节 '{section}' 应为 dict")
                elif not isinstance(config[section].get("fields", []), list):
                    bundle.errors.append(f"config.yaml 子节 'state_schema.fields' 应为列表")
            else:
                if not isinstance(config[section], list):
                    bundle.errors.append(f"config.yaml 子节 '{section}' 应为列表")

        # 4. 校验数据目录存在
        if not os.path.isdir(bundle.chapters_dir):
            bundle.errors.append(f"chapters 目录不存在: {bundle.chapters_dir}")
        if not os.path.isdir(bundle.npcs_dir):
            bundle.errors.append(f"npcs 目录不存在: {bundle.npcs_dir}")

        if bundle.errors:
            logger.warning(f"题材包 {bundle.theme_id} 加载完成但有 {len(bundle.errors)} 个错误")
        else:
            logger.info(f"题材包加载成功: {bundle.theme_id} ({bundle.theme_name})")

        return bundle

    @lru_cache(maxsize=8)
    def load_chapter_from(self, chapters_dir: str, stage_id: str) -> Optional[Dict[str, Any]]:
        """从指定章节目录加载章节"""
        if not os.path.isdir(chapters_dir):
            return None
        for fname in os.listdir(chapters_dir):
            if not fname.endswith(".yaml"):
                continue
            fpath = os.path.join(chapters_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and data.get("stage_id") == stage_id:
                    return data
            except Exception as e:
                logger.error(f"加载章节失败 {fname}: {e}")
        return None

    @lru_cache(maxsize=16)
    def load_npc_from(self, npcs_dir: str, npc_id: str) -> Optional[Dict[str, Any]]:
        """从指定 NPC 目录加载 NPC YAML"""
        yaml_path = os.path.join(npcs_dir, f"npc_{npc_id}.yaml")
        if not os.path.exists(yaml_path):
            return None
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"NPC YAML 解析失败 {npc_id}: {e}")
            return None

    def list_npcs_from(self, npcs_dir: str) -> List[str]:
        """列出 NPC 目录下所有 npc_id"""
        if not os.path.isdir(npcs_dir):
            return []
        result = []
        for fname in sorted(os.listdir(npcs_dir)):
            if fname.startswith("npc_") and fname.endswith(".yaml"):
                result.append(fname[4:-5])  # 去掉 npc_ 前缀和 .yaml 后缀
        return result

    # --------------------------------------------------------
    # 内部工具
    # --------------------------------------------------------

    def _load_yaml(self, path: str) -> Optional[Dict[str, Any]]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析失败 {path}: {e}")
            return None

    def _resolve_subdir(
        self,
        manifest: Dict[str, Any],
        manifest_key: str,
        default_subdir: str,
        data_root: str,
        theme_dir: str,
    ) -> str:
        """从 manifest 解析子目录路径，支持绝对/相对路径"""
        val = manifest.get(manifest_key, default_subdir)
        if not val:
            return ""
        if os.path.isabs(val):
            return val
        # 优先在 data_root 下找
        candidate = os.path.join(data_root, val)
        if os.path.isdir(candidate):
            return candidate
        # 退化到 theme_dir 下
        return os.path.join(theme_dir, val)
