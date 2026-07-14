"""认证模块 — JWT 登录与用户信息。"""

from functools import wraps

import jwt
from flask import Blueprint, g, jsonify, request

import config
import models

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def create_token(user: dict) -> str:
    payload = {"sub": str(user["id"]), "name": user["name"], "role": user["role"]}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip()
        if not token:
            return jsonify({"message": "未提供认证令牌"}), 401
        payload = decode_token(token)
        if payload is None:
            return jsonify({"message": "认证令牌无效或已过期"}), 401
        g.user_id = int(payload["sub"])
        g.user_name = payload.get("name", "")
        return f(*args, **kwargs)
    return decorated


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()
    if not username or not password:
        return jsonify({"message": "用户名和密码不能为空"}), 400
    user = models.verify_login(username, password)
    if user is None:
        return jsonify({"message": "用户名或密码错误"}), 401
    return jsonify({
        "token": create_token(user),
        "user": {"id": user["id"], "name": user["name"], "role": user["role"]},
    })


@auth_bp.get("/me")
@login_required
def me():
    user = models.get_user_by_id(g.user_id)
    if user is None:
        return jsonify({"message": "用户不存在"}), 404
    return jsonify(user)
