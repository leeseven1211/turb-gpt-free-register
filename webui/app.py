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

from core import (
    admin_repository,
    account_task_store,
    codex_operation_service,
    codex_retry_service,
    codex_token_refresh_service,
    db,
    deactivation_mail_service,
    extract_link_service,
    live_check_service,
    operation_task_store,
    plan_check_service,
    sms_provider,
)
from core import registration_service as svc
from core.task_errors import classify_task_error
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
from webui.routes.integrations import create_integrations_blueprint
from webui.routes.jobs import create_jobs_blueprint
from webui.routes.operations import create_operations_blueprint

logger = logging.getLogger(__name__)


def create_app(auth_code: str | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")
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
        create_codex_blueprint,
        create_integrations_blueprint,
    ):
        app.register_blueprint(factory(context))
    return app
