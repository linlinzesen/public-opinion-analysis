"""个人中心模块 — 关注平台 / 关键词管理。"""

from flask import Blueprint, g, jsonify, request

import models
from auth import login_required

profile_bp = Blueprint("profile", __name__, url_prefix="/user")


# ── 关注平台 ──────────────────────────────────────────────

@profile_bp.get("/follow-platforms")
@login_required
def list_platforms():
    return jsonify(models.get_platforms(g.user_id))


@profile_bp.post("/follow-platforms")
@login_required
def add_platform():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    if not name or not url:
        return jsonify({"message": "平台名称和 URL 不能为空"}), 400
    result = models.add_platform(g.user_id, name, url)
    return jsonify(result), 201


@profile_bp.delete("/follow-platforms/<int:platform_id>")
@login_required
def remove_platform(platform_id: int):
    ok = models.delete_platform(platform_id, g.user_id)
    if not ok:
        return jsonify({"message": "平台不存在或无权操作"}), 404
    return jsonify({"success": True})


# ── 关注关键词 ────────────────────────────────────────────

@profile_bp.get("/follow-keywords")
@login_required
def list_keywords():
    return jsonify(models.get_keywords(g.user_id))


@profile_bp.post("/follow-keywords")
@login_required
def add_keyword():
    data = request.get_json(silent=True) or {}
    word = (data.get("word") or "").strip()
    level = (data.get("level") or "中").strip()
    if not word:
        return jsonify({"message": "关键词不能为空"}), 400
    if level not in ("高", "中", "低"):
        level = "中"
    result = models.add_keyword(g.user_id, word, level)
    return jsonify(result), 201


@profile_bp.delete("/follow-keywords/<int:keyword_id>")
@login_required
def remove_keyword(keyword_id: int):
    ok = models.delete_keyword(keyword_id, g.user_id)
    if not ok:
        return jsonify({"message": "关键词不存在或无权操作"}), 404
    return jsonify({"success": True})


# ── 修改密码 ──────────────────────────────────────────────

@profile_bp.post("/change-password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_password = (data.get("oldPassword") or "").strip()
    new_password = (data.get("newPassword") or "").strip()
    if not old_password or not new_password:
        return jsonify({"message": "新旧密码不能为空"}), 400
    if len(new_password) < 6:
        return jsonify({"message": "新密码长度不能少于 6 位"}), 400
    if old_password == new_password:
        return jsonify({"message": "新密码不能与旧密码相同"}), 400
    ok = models.change_password(g.user_id, old_password, new_password)
    if not ok:
        return jsonify({"message": "旧密码验证失败"}), 401
    return jsonify({"success": True, "message": "密码修改成功"})
