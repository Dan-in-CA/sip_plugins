# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""SIP plugin providing an MCP Streamable HTTP endpoint."""

import json
import time

import gv
from helpers import (
    jsave,
    password_hash,
    read_log,
    report_rain_delay_change,
    run_once,
    run_program,
    stop_onrain,
    stop_stations,
)
from sip import template_render
from urls import urls
import web
from webpages import ProtectedPage

from mcp_server_protocol import (
    DEFAULT_PROTOCOL_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    JsonRpcError,
    SessionStore,
    classify_message,
    make_error,
    make_result,
    negotiate_protocol_version,
)


DATA_FILE = "./data/mcp_server.json"
PLUGIN_NAME = "MCP Server"
MCP_ENDPOINT = "/mcp"


DEFAULT_SETTINGS = {
    "enabled": "on",
    "require_auth": "off",
    "require_origin": "off",
    "allowed_origins": "http://localhost,http://127.0.0.1",
}


SESSION_STORE = SessionStore()


# fmt: off
urls.extend([
    "/mcp-settings", "plugins.mcp_server.settings",
    "/mcp-save", "plugins.mcp_server.save_settings",
    MCP_ENDPOINT, "plugins.mcp_server.mcp_endpoint",
])
# fmt: on

gv.plugin_menu.append([_(u"MCP Server"), u"/mcp-settings"])


def _load_settings():
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(DATA_FILE, "r") as f:
            file_settings = json.load(f)
            if isinstance(file_settings, dict):
                settings.update(file_settings)
    except IOError:
        pass
    return settings


def _save_settings(settings):
    with open(DATA_FILE, "w") as f:
        json.dump(settings, f, indent=4, sort_keys=True)


def _origin_allowed(settings):
    if settings.get("require_origin") != "on":
        return True

    origin = web.ctx.env.get("HTTP_ORIGIN")
    if not origin:
        return True

    allowlist = [
        item.strip()
        for item in settings.get("allowed_origins", "").split(",")
        if item.strip()
    ]
    return origin in allowlist


def _is_authenticated(settings):
    if settings.get("require_auth") != "on":
        return True

    # If SIP passphrase is disabled, SIP itself is open.
    if int(gv.sd.get("upas", 0)) == 0:
        return True

    # Browser session auth.
    try:
        if web.config._session.user == "admin":
            return True
    except Exception:
        pass

    # Header-based passphrase auth.
    supplied = web.ctx.env.get("HTTP_X_SIP_PASSPHRASE", "")
    if not supplied:
        auth_header = web.ctx.env.get("HTTP_AUTHORIZATION", "")
        if auth_header.lower().startswith("bearer "):
            supplied = auth_header[7:].strip()

    if not supplied:
        return False

    return password_hash(supplied) == gv.sd.get("passphrase", "")


def _http_json(status, payload):
    web.ctx.status = status
    web.header("Content-Type", "application/json")
    return json.dumps(payload)


def _is_http_protocol_error(err):
    if err.code == -32600 and err.message == "Unsupported MCP protocol version":
        return True
    return False


def _station_exists(station_id):
    return isinstance(station_id, int) and 1 <= station_id <= int(gv.sd.get("nst", 0))


def _tool_get_system_status(_args):
    return {
        "name": gv.sd.get("name"),
        "enabled": gv.sd.get("en"),
        "manual_mode": gv.sd.get("mm"),
        "busy": gv.sd.get("bsy"),
        "rain_delay_hours": gv.sd.get("rd"),
        "rain_delay_until": gv.sd.get("rdst"),
        "rain_sensed": gv.sd.get("rs"),
        "water_level": gv.sd.get("wl"),
        "station_count": gv.sd.get("nst"),
        "running_program": gv.pon,
        "timestamp": int(time.time()),
    }


def _tool_list_stations(_args):
    stations = []
    for sid in range(gv.sd["nst"]):
        bid = sid // 8
        bit = sid % 8
        visible = 1 if (gv.sd["show"][bid] >> bit) & 1 else 0
        ignore_rain = 1 if (gv.sd["ir"][bid] >> bit) & 1 else 0
        requires_master = 1 if (gv.sd["mo"][bid] >> bit) & 1 else 0

        remaining = gv.ps[sid][1] if sid < len(gv.ps) else 0
        if remaining == float("inf"):
            remaining = None

        stations.append(
            {
                "station_id": sid + 1,
                "name": gv.snames[sid] if sid < len(gv.snames) else "",
                "is_on": 1 if gv.srvals[sid] else 0,
                "remaining_sec": remaining,
                "is_master": 1 if gv.sd.get("mas", 0) == sid + 1 else 0,
                "visible": visible,
                "ignore_rain": ignore_rain,
                "requires_master": requires_master,
            }
        )
    return {"stations": stations}


def _tool_list_programs(_args):
    programs = []
    for idx, prog in enumerate(gv.pd):
        programs.append(
            {
                "program_id": idx + 1,
                "name": prog.get("name", ""),
                "enabled": prog.get("enabled", 0),
                "type": prog.get("type", ""),
                "start_min": prog.get("start_min", 0),
                "stop_min": prog.get("stop_min", 0),
                "cycle_min": prog.get("cycle_min", 0),
            }
        )
    return {"programs": programs}


def _tool_run_station(args):
    station_id = int(args.get("station_id", 0))
    duration_sec = int(args.get("duration_sec", 0))
    preempt = bool(args.get("preempt", True))

    if not _station_exists(station_id):
        raise JsonRpcError(-32602, "Invalid station_id")
    if duration_sec <= 0:
        raise JsonRpcError(-32602, "duration_sec must be > 0")

    gv.rovals = [0] * gv.sd["nst"]
    gv.rovals[station_id - 1] = duration_sec
    run_once(bump=1 if preempt else 0, pnum=98)

    return {
        "ok": True,
        "station_id": station_id,
        "duration_sec": duration_sec,
        "preempt": preempt,
    }


def _tool_stop_all_stations(_args):
    stop_stations()
    return {"ok": True}


def _tool_run_program_now(args):
    program_id = int(args.get("program_id", 0))
    if program_id <= 0 or program_id > len(gv.pd):
        raise JsonRpcError(-32602, "Invalid program_id")
    run_program(program_id - 1)
    return {"ok": True, "program_id": program_id}


def _tool_set_rain_delay(args):
    hours = float(args.get("hours", 0))
    if hours < 0:
        raise JsonRpcError(-32602, "hours must be >= 0")

    gv.sd["rd"] = hours
    if hours > 0:
        gv.sd["rdst"] = round(gv.now + (hours * 3600))
        stop_onrain()
    else:
        gv.sd["rdst"] = 0
    jsave(gv.sd, "sd")
    report_rain_delay_change()

    return {"ok": True, "hours": hours, "rain_delay_until": gv.sd["rdst"]}


def _tool_set_water_level(args):
    percent = int(args.get("percent", -1))
    if percent < 0 or percent > 200:
        raise JsonRpcError(-32602, "percent must be in range 0..200")
    gv.sd["wl"] = percent
    jsave(gv.sd, "sd")
    return {"ok": True, "percent": percent}


def _tool_get_logs(args):
    date = args.get("date")
    limit = int(args.get("limit", 50))
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    records = read_log()
    if date:
        records = [r for r in records if r.get("date") == date]
    return {"records": records[:limit], "count": min(limit, len(records))}


TOOLS = {
    "get_system_status": _tool_get_system_status,
    "list_stations": _tool_list_stations,
    "list_programs": _tool_list_programs,
    "run_station": _tool_run_station,
    "stop_all_stations": _tool_stop_all_stations,
    "run_program_now": _tool_run_program_now,
    "set_rain_delay": _tool_set_rain_delay,
    "set_water_level": _tool_set_water_level,
    "get_logs": _tool_get_logs,
}


TOOL_SPECS = [
    {
        "name": "get_system_status",
        "description": "Get current SIP controller status.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_stations",
        "description": "List station metadata and live state.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_programs",
        "description": "List configured SIP programs.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_station",
        "description": "Run a station for a duration in seconds.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "station_id": {"type": "integer", "minimum": 1},
                "duration_sec": {"type": "integer", "minimum": 1},
                "preempt": {"type": "boolean"},
            },
            "required": ["station_id", "duration_sec"],
            "additionalProperties": False,
        },
    },
    {
        "name": "stop_all_stations",
        "description": "Stop all running stations immediately.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_program_now",
        "description": "Run a SIP program immediately by program id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "program_id": {"type": "integer", "minimum": 1},
            },
            "required": ["program_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_rain_delay",
        "description": "Set rain delay in hours. Use 0 to clear.",
        "inputSchema": {
            "type": "object",
            "properties": {"hours": {"type": "number", "minimum": 0}},
            "required": ["hours"],
            "additionalProperties": False,
        },
    },
    {
        "name": "set_water_level",
        "description": "Set SIP water level percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {"percent": {"type": "integer", "minimum": 0, "maximum": 200}},
            "required": ["percent"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_logs",
        "description": "Get recent run log records.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Optional YYYY-MM-DD date filter."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
            },
            "additionalProperties": False,
        },
    },
]


def _get_session_or_error():
    session_id = web.ctx.env.get("HTTP_MCP_SESSION_ID", "")
    if not session_id:
        raise JsonRpcError(-32002, "Missing MCP-Session-Id header")
    session = SESSION_STORE.get(session_id)
    if not session:
        raise JsonRpcError(-32002, "Invalid or expired session")
    SESSION_STORE.touch(session_id)
    return session_id, session


def _enforce_protocol_version(session=None):
    protocol_version = web.ctx.env.get("HTTP_MCP_PROTOCOL_VERSION")
    if protocol_version and protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise JsonRpcError(-32600, "Unsupported MCP protocol version")

    if protocol_version and session and protocol_version != session.get("protocol_version"):
        raise JsonRpcError(-32600, "Protocol version does not match session")


def _handle_request(req):
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise JsonRpcError(-32602, "params must be an object", req_id=req_id)

    if method == "initialize":
        requested_version = params.get("protocolVersion")
        negotiated = negotiate_protocol_version(requested_version)
        session_id = SESSION_STORE.create(negotiated)
        web.header("MCP-Session-Id", session_id)

        result = {
            "protocolVersion": negotiated,
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "sip-mcp-server",
                "version": "0.1.0",
            },
        }
        return make_result(req_id, result)

    session_id, session = _get_session_or_error()
    _enforce_protocol_version(session)

    if method == "ping":
        return make_result(req_id, {})

    if method == "tools/list":
        return make_result(req_id, {"tools": TOOL_SPECS})

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            raise JsonRpcError(-32602, "Unknown tool", data={"name": tool_name}, req_id=req_id)
        if tool_args is None:
            tool_args = {}
        if not isinstance(tool_args, dict):
            raise JsonRpcError(-32602, "Tool arguments must be object", req_id=req_id)
        payload = TOOLS[tool_name](tool_args)
        return make_result(
            req_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload),
                    }
                ],
                "isError": False,
            },
        )

    raise JsonRpcError(-32601, "Method not found", req_id=req_id)


def _handle_notification(note):
    method = note.get("method")
    if method == "notifications/initialized":
        session_id = web.ctx.env.get("HTTP_MCP_SESSION_ID", "")
        if session_id:
            SESSION_STORE.mark_initialized(session_id)


class settings(ProtectedPage):
    """Render MCP plugin settings page."""

    def GET(self):
        return template_render.mcp_server(_load_settings(), MCP_ENDPOINT)


class save_settings(ProtectedPage):
    """Save MCP plugin settings."""

    def GET(self):
        qdict = web.input()
        settings = _load_settings()

        settings["enabled"] = "on" if qdict.get("enabled") in ("on", "1") else "off"
        settings["require_auth"] = "on" if qdict.get("require_auth") in ("on", "1") else "off"
        settings["require_origin"] = "on" if qdict.get("require_origin") in ("on", "1") else "off"
        settings["allowed_origins"] = qdict.get("allowed_origins", "").strip()

        _save_settings(settings)
        raise web.seeother("/")


class mcp_endpoint(object):
    """MCP Streamable HTTP endpoint (POST only in v1)."""

    def POST(self):
        settings = _load_settings()

        if settings.get("enabled") != "on":
            return _http_json("503 Service Unavailable", {"error": "MCP plugin disabled"})

        if not _origin_allowed(settings):
            return _http_json("403 Forbidden", {"error": "Origin not allowed"})

        if not _is_authenticated(settings):
            return _http_json(
                "401 Unauthorized",
                make_error(None, -32001, "Unauthorized"),
            )

        try:
            raw = web.data()
            message = json.loads(raw.decode("utf-8"))
            message_type = classify_message(message)

            if message_type in ("notification", "response"):
                if message_type == "notification":
                    _handle_notification(message)
                web.ctx.status = "202 Accepted"
                return ""

            _enforce_protocol_version()
            response = _handle_request(message)
            return _http_json("200 OK", response)

        except JsonRpcError as e:
            req_id = None
            try:
                req_id = message.get("id")
            except Exception:
                req_id = e.req_id
            status = "400 Bad Request" if _is_http_protocol_error(e) else "200 OK"
            return _http_json(status, make_error(req_id, e.code, e.message, e.data))
        except ValueError:
            return _http_json("400 Bad Request", make_error(None, -32600, "Invalid JSON body"))
        except Exception as e:
            return _http_json("200 OK", make_error(None, -32603, "Internal error", data=str(e)))

    def GET(self):
        web.ctx.status = "405 Method Not Allowed"
        return ""

    def DELETE(self):
        session_id = web.ctx.env.get("HTTP_MCP_SESSION_ID", "")
        if not session_id:
            web.ctx.status = "400 Bad Request"
            return ""
        if SESSION_STORE.delete(session_id):
            web.ctx.status = "204 No Content"
            return ""
        web.ctx.status = "404 Not Found"
        return ""


# Ensure settings file exists with defaults.
try:
    with open(DATA_FILE, "r"):
        pass
except IOError:
    jsave(DEFAULT_SETTINGS, "mcp_server")
