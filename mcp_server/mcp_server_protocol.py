"""Shared protocol helpers for MCP Server plugin."""

import time
import uuid


JSONRPC_VERSION = "2.0"
SUPPORTED_PROTOCOL_VERSIONS = ("2025-11-25", "2025-03-26")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


class JsonRpcError(Exception):
    def __init__(self, code, message, data=None, req_id=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
        self.req_id = req_id


def make_result(req_id, result):
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "result": result}


def make_error(req_id, code, message, data=None):
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": JSONRPC_VERSION, "id": req_id, "error": error}


def validate_jsonrpc_message(msg):
    if not isinstance(msg, dict):
        raise JsonRpcError(-32600, "Invalid Request: message must be object")
    if msg.get("jsonrpc") != JSONRPC_VERSION:
        raise JsonRpcError(-32600, "Invalid Request: jsonrpc must be '2.0'")


def classify_message(msg):
    """
    Return one of: request, notification, response.
    Raise JsonRpcError for invalid combinations.
    """

    validate_jsonrpc_message(msg)

    has_method = "method" in msg
    has_id = "id" in msg
    has_result = "result" in msg
    has_error = "error" in msg

    if has_method and (has_result or has_error):
        raise JsonRpcError(-32600, "Invalid Request: method and result/error cannot coexist")

    if has_method:
        if not isinstance(msg["method"], str):
            raise JsonRpcError(-32600, "Invalid Request: method must be string")
        return "request" if has_id else "notification"

    if has_result and has_error:
        raise JsonRpcError(-32600, "Invalid Request: both result and error present")

    if has_result or has_error:
        if not has_id:
            raise JsonRpcError(-32600, "Invalid Request: response must include id")
        return "response"

    raise JsonRpcError(-32600, "Invalid Request: unknown message shape")


def negotiate_protocol_version(requested):
    if requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return DEFAULT_PROTOCOL_VERSION


class SessionStore:
    def __init__(self, ttl_seconds=12 * 3600):
        self.ttl_seconds = ttl_seconds
        self._sessions = {}

    def create(self, protocol_version):
        sid = uuid.uuid4().hex
        now = time.time()
        self._sessions[sid] = {
            "protocol_version": protocol_version,
            "created_at": now,
            "updated_at": now,
            "initialized": False,
        }
        return sid

    def get(self, session_id):
        self._cleanup()
        return self._sessions.get(session_id)

    def touch(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id]["updated_at"] = time.time()

    def mark_initialized(self, session_id):
        if session_id in self._sessions:
            self._sessions[session_id]["initialized"] = True
            self.touch(session_id)

    def delete(self, session_id):
        return self._sessions.pop(session_id, None) is not None

    def _cleanup(self):
        now = time.time()
        stale = []
        for sid, meta in self._sessions.items():
            if now - meta.get("updated_at", now) > self.ttl_seconds:
                stale.append(sid)
        for sid in stale:
            self._sessions.pop(sid, None)
