# -*- coding: utf-8 -*-
"""Flask application assembly for the local WebUI.

Domain route handlers live in `webui/routes/`; this module keeps the public
application factory and a few compatibility imports used by existing tests and
integrations.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse

import pyotp
from flask import Flask

from core.storage import admin_repository
from core import account_task_store
from core.codex import operation_service as codex_operation_service, retry_service as codex_retry_service, token_refresh_service as codex_token_refresh_service
from core import db
from core.accounts.deactivation import mail_scan as deactivation_mail_service
from core.extract_link import service as extract_link_service
from core.accounts.liveness import service as live_check_service
from core import operation_task_store
from core.accounts.plans import service as plan_check_service
from core.sms import provider as sms_provider
from core.registration import service as svc
from core.operations.errors import classify_task_error
from config import codex as codex_config
from webui import config_editor
from webui.auth import init_auth, register_auth_routes
from webui.route_helpers import _compact_job_for_list, _latest_progress_batch
from webui.runtime import WebUIContext
from webui.routes.accounts import create_accounts_blueprint
from webui.routes.codex import create_codex_blueprint
from webui.routes.config import create_config_blueprint
from webui.routes.dashboard import create_dashboard_blueprint
from webui.routes.email_pool import create_email_pool_blueprint
from webui.routes.extract_workbench import create_extract_workbench_blueprint
from webui.routes.integrations import create_integrations_blueprint
from webui.routes.jobs import create_jobs_blueprint
from webui.routes.operations import create_operations_blueprint
from webui.routes.proxy_traffic import create_proxy_traffic_blueprint
from webui.routes.health import create_health_blueprint

logger = logging.getLogger(__name__)


def create_app(auth_code: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
    # Keep static bundles in the browser cache for a short, explicit window so
    # switching/reopening the console does not re-download several hundred KB
    # of CSS/JS on every visit.
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 300
    init_auth(app, auth_code=auth_code)
    register_auth_routes(app)

    context = WebUIContext(app=app, logger=logger)
    for factory in (
        create_dashboard_blueprint,
        create_config_blueprint,
        create_email_pool_blueprint,
        create_accounts_blueprint,
        create_jobs_blueprint,
        create_operations_blueprint,
        create_proxy_traffic_blueprint,
        create_codex_blueprint,
        create_integrations_blueprint,
        create_extract_workbench_blueprint,
        create_health_blueprint,
    ):
        app.register_blueprint(factory(context))
    return app
