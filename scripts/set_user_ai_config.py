#!/usr/bin/env python3
"""
用户大模型配置管理脚本（管理员用）

当后端关闭自助配置（AI_CONFIG_SELF_SERVICE 未开启，默认关闭）时，
每个用户的大模型配置只能通过数据库维护。此脚本按用户名/邮箱直接
读写 settings 表中与该账号关联的那一行，避免手写 SQL。

使用方法:
    # 列出所有用户及其配置概览
    python scripts/set_user_ai_config.py list

    # 查看某个用户的大模型配置
    python scripts/set_user_ai_config.py show --user alice

    # 设置某个用户的全局提供商与凭证
    python scripts/set_user_ai_config.py set --user alice \
        --provider openai \
        --api-base-url https://api.example.com/v1 \
        --api-key sk-xxxx \
        --text-model gpt-4o \
        --image-model gpt-image-1 \
        --caption-model gpt-4o-mini

    # 单独设置某个模型角色的提供商/凭证（不影响其他角色）
    python scripts/set_user_ai_config.py set --user alice \
        --text-source openai --text-api-key sk-xxx --text-api-base-url https://...

    # 设置 LazyLLM 厂商 Key（可多次传入）
    python scripts/set_user_ai_config.py set --user alice \
        --lazyllm-key qwen=sk-aaa --lazyllm-key doubao=sk-bbb

    # 清空某个用户的若干字段（回退到 .env 默认值）
    python scripts/set_user_ai_config.py clear --user alice --fields api_key,api_base_url

数据库位置由 backend/.env / 环境变量决定，与后端服务一致。
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# 与 backend/controllers/settings_controller.py 的 AI_CONFIG_FIELDS 保持一致
SETTABLE_FIELDS = {
    "provider": "ai_provider_format",
    "api_base_url": "api_base_url",
    "api_key": "api_key",
    "text_model": "text_model",
    "image_model": "image_model",
    "caption_model": "image_caption_model",
    "text_source": "text_model_source",
    "image_source": "image_model_source",
    "caption_source": "image_caption_model_source",
    "text_api_key": "text_api_key",
    "text_api_base_url": "text_api_base_url",
    "image_api_key": "image_api_key",
    "image_api_base_url": "image_api_base_url",
    "caption_api_key": "image_caption_api_key",
    "caption_api_base_url": "image_caption_api_base_url",
    "image_api_protocol": "openai_image_api_protocol",
}

CLEARABLE_FIELDS = set(SETTABLE_FIELDS.values()) | {"lazyllm_api_keys"}


def _mask(value):
    if not value:
        return "-"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]} (len={len(value)})"


def _find_user(User, identifier):
    from sqlalchemy import or_

    user = User.query.filter(
        or_(User.username == identifier, User.email == identifier.lower())
    ).first()
    if not user:
        print(f"错误: 找不到用户 '{identifier}'（用户名或邮箱）", file=sys.stderr)
        sys.exit(1)
    return user


def _get_settings(db, Settings, user):
    settings = Settings.query.filter_by(user_id=user.id).first()
    if settings is None:
        settings = Settings(user_id=user.id)
        db.session.add(settings)
        db.session.flush()
    return settings


def _print_config(user, settings):
    print(f"用户: {user.username}  (id={user.id}, email={user.email or '-'})")
    rows = [
        ("提供商格式 (ai_provider_format)", settings.ai_provider_format or "-"),
        ("API Base URL", settings.api_base_url or "-"),
        ("API Key", _mask(settings.api_key)),
        ("文本模型", settings.text_model or "-"),
        ("图像模型", settings.image_model or "-"),
        ("图片识别模型", settings.image_caption_model or "-"),
        ("文本模型提供商", settings.text_model_source or "-"),
        ("图像模型提供商", settings.image_model_source or "-"),
        ("图片识别模型提供商", settings.image_caption_model_source or "-"),
        ("文本模型 API Key", _mask(settings.text_api_key)),
        ("文本模型 Base URL", settings.text_api_base_url or "-"),
        ("图像模型 API Key", _mask(settings.image_api_key)),
        ("图像模型 Base URL", settings.image_api_base_url or "-"),
        ("图片识别 API Key", _mask(settings.image_caption_api_key)),
        ("图片识别 Base URL", settings.image_caption_api_base_url or "-"),
        ("OpenAI 图像协议", settings.openai_image_api_protocol or "auto"),
    ]
    lazyllm = settings.get_lazyllm_api_keys_dict()
    rows.append((
        "LazyLLM 厂商 Key",
        ", ".join(f"{v}={_mask(k)}" for v, k in lazyllm.items()) if lazyllm else "-",
    ))
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        print(f"  {label.ljust(width)} : {value}")
    print("  （值为 '-' 的字段会回退到后端 .env 的默认配置）")


def cmd_list(app, db, User, Settings, _args):
    with app.app_context():
        users = User.query.order_by(User.created_at).all()
        if not users:
            print("没有用户")
            return
        for user in users:
            settings = Settings.query.filter_by(user_id=user.id).first()
            if settings:
                summary = (
                    f"provider={settings.ai_provider_format or '(env)'} "
                    f"text={settings.text_model or '(env)'} "
                    f"image={settings.image_model or '(env)'} "
                    f"key={'已设置' if settings.api_key else '(env)'}"
                )
            else:
                summary = "尚无配置行（首次登录/设置时自动创建）"
            active = "" if user.is_active else "  [已停用]"
            print(f"- {user.username}  ({user.email or '无邮箱'}){active}")
            print(f"    {summary}")


def cmd_show(app, db, User, Settings, args):
    with app.app_context():
        user = _find_user(User, args.user)
        settings = _get_settings(db, Settings, user)
        db.session.commit()
        _print_config(user, settings)


def cmd_set(app, db, User, Settings, args):
    with app.app_context():
        user = _find_user(User, args.user)
        settings = _get_settings(db, Settings, user)

        changed = []
        for arg_name, column in SETTABLE_FIELDS.items():
            value = getattr(args, arg_name, None)
            if value is None:
                continue
            setattr(settings, column, value.strip() or None)
            changed.append(column)

        if args.lazyllm_key:
            keys = settings.get_lazyllm_api_keys_dict()
            for item in args.lazyllm_key:
                if "=" not in item:
                    print(f"错误: --lazyllm-key 需要 vendor=key 格式，收到 '{item}'", file=sys.stderr)
                    sys.exit(1)
                vendor, key = item.split("=", 1)
                if key:
                    keys[vendor.strip().lower()] = key
                else:
                    keys.pop(vendor.strip().lower(), None)
            settings.lazyllm_api_keys = json.dumps(keys) if keys else None
            changed.append("lazyllm_api_keys")

        if not changed:
            print("没有要更新的字段，运行 --help 查看可用参数")
            return

        db.session.commit()
        print(f"已更新 {user.username} 的字段: {', '.join(changed)}")
        print("提示: 后端会在该用户下次请求时自动加载新配置。")
        _print_config(user, settings)


def cmd_clear(app, db, User, Settings, args):
    with app.app_context():
        user = _find_user(User, args.user)
        settings = _get_settings(db, Settings, user)

        fields = [f.strip() for f in args.fields.split(",") if f.strip()]
        unknown = [f for f in fields if f not in CLEARABLE_FIELDS]
        if unknown:
            print(f"错误: 未知字段 {unknown}", file=sys.stderr)
            print(f"可清空的字段: {', '.join(sorted(CLEARABLE_FIELDS))}", file=sys.stderr)
            sys.exit(1)

        for field in fields:
            setattr(settings, field, None)
        db.session.commit()
        print(f"已清空 {user.username} 的字段: {', '.join(fields)}（回退到 .env 默认值）")


def main():
    parser = argparse.ArgumentParser(description="管理每个用户账号关联的大模型配置（settings 表）")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="列出所有用户及配置概览")

    p_show = sub.add_parser("show", help="查看某个用户的大模型配置")
    p_show.add_argument("--user", required=True, help="用户名或邮箱")

    p_set = sub.add_parser("set", help="设置某个用户的大模型配置")
    p_set.add_argument("--user", required=True, help="用户名或邮箱")
    p_set.add_argument("--provider", help="提供商格式: openai / gemini / lazyllm / codex 或 lazyllm 厂商名")
    p_set.add_argument("--api-base-url", dest="api_base_url", help="全局 API Base URL")
    p_set.add_argument("--api-key", dest="api_key", help="全局 API Key")
    p_set.add_argument("--text-model", dest="text_model", help="文本模型名称")
    p_set.add_argument("--image-model", dest="image_model", help="图像模型名称")
    p_set.add_argument("--caption-model", dest="caption_model", help="图片识别模型名称")
    p_set.add_argument("--text-source", dest="text_source", help="文本模型提供商 (gemini/openai/qwen/...)")
    p_set.add_argument("--image-source", dest="image_source", help="图像模型提供商")
    p_set.add_argument("--caption-source", dest="caption_source", help="图片识别模型提供商")
    p_set.add_argument("--text-api-key", dest="text_api_key", help="文本模型独立 API Key")
    p_set.add_argument("--text-api-base-url", dest="text_api_base_url", help="文本模型独立 Base URL")
    p_set.add_argument("--image-api-key", dest="image_api_key", help="图像模型独立 API Key")
    p_set.add_argument("--image-api-base-url", dest="image_api_base_url", help="图像模型独立 Base URL")
    p_set.add_argument("--caption-api-key", dest="caption_api_key", help="图片识别模型独立 API Key")
    p_set.add_argument("--caption-api-base-url", dest="caption_api_base_url", help="图片识别模型独立 Base URL")
    p_set.add_argument("--image-api-protocol", dest="image_api_protocol", choices=["auto", "images", "chat"], help="OpenAI 图像 API 协议")
    p_set.add_argument("--lazyllm-key", action="append", help="LazyLLM 厂商 Key，格式 vendor=key，可重复；vendor= 空值表示删除")

    p_clear = sub.add_parser("clear", help="清空某个用户的字段（回退 .env 默认）")
    p_clear.add_argument("--user", required=True, help="用户名或邮箱")
    p_clear.add_argument("--fields", required=True, help="逗号分隔的字段名，如 api_key,api_base_url")

    args = parser.parse_args()

    from app import create_app
    from models import db, Settings, User

    app = create_app()

    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "set": cmd_set,
        "clear": cmd_clear,
    }
    handlers[args.command](app, db, User, Settings, args)


if __name__ == "__main__":
    main()
