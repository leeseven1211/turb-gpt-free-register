# -*- coding: utf-8 -*-
"""Blueprint primitives used by the WebUI route modules.

The legacy console exposes endpoint names as part of its internal URL contract.
Flask normally prefixes Blueprint endpoints, so this small setup-state override
keeps the existing names while still allowing routes to be registered by domain.
"""
from __future__ import annotations

from typing import Any

from flask import Blueprint
from flask.blueprints import BlueprintSetupState


class _LegacyEndpointSetupState(BlueprintSetupState):
    def add_url_rule(
        self,
        rule: str,
        endpoint: str | None = None,
        view_func: Any | None = None,
        **options: Any,
    ) -> None:
        if self.url_prefix is not None:
            if rule:
                rule = "/".join((self.url_prefix.rstrip("/"), rule.lstrip("/")))
            else:
                rule = self.url_prefix
        options.setdefault("subdomain", self.subdomain)
        if endpoint is None:
            endpoint = getattr(view_func, "__name__", None)
        defaults = self.url_defaults
        if "defaults" in options:
            defaults = dict(defaults, **options.pop("defaults"))
        self.app.add_url_rule(
            rule,
            endpoint,
            view_func,
            defaults=defaults,
            **options,
        )


class LegacyEndpointBlueprint(Blueprint):
    """A regular Flask Blueprint whose routes retain their legacy endpoints."""

    def make_setup_state(
        self,
        app: Any,
        options: dict[str, Any],
        first_registration: bool = False,
    ) -> BlueprintSetupState:
        return _LegacyEndpointSetupState(self, app, options, first_registration)
