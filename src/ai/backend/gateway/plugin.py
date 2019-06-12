import asyncio
from collections import defaultdict
import logging
import pkg_resources
from types import ModuleType
from typing import Any, Awaitable, Callable, List, Iterable, Mapping, Sequence, Tuple

from aiohttp import web
import aiohttp_cors

from ai.backend.common.logging import BraceStyleAdapter
from ..manager.plugin.abc import AbstractHook
from ..manager.plugin.types import HookEventTypes, HookResult

log = BraceStyleAdapter(logging.getLogger('ai.backend.gateway.plugin'))

WebMiddleware = Callable[[web.Request, web.Response], None]


def load_webapp_plugins(cors_options: Mapping[str, aiohttp_cors.ResourceOptions]):
    entry_prefix = 'backendai_manager_webapp_v10'
    webapp_plugin_ctx = WebAppPluginContext(cors_options)
    # TODO: ensure some specific ordering?
    for entrypoint in pkg_resources.iter_entry_points(entry_prefix):
        log.info('Loading webapp plugin from {}', entrypoint)
        webapp_plugin_ctx.add_plugin(entrypoint.load())
    return webapp_plugin_ctx


def load_hook_plugins():
    entry_prefix = 'backendai_manager_hook_v10'
    hook_plugin_ctx = HookPluginContext()
    # TODO: ensure some specific ordering?
    for entrypoint in pkg_resources.iter_entry_points(entry_prefix):
        log.info('Loading hook plugin from {}', entrypoint)
        hook_plugin_ctx.add_plugin(entrypoint.load())
    return hook_plugin_ctx


class WebAppPluginContext:

    _plugins: List[ModuleType]
    _initialized: bool

    def __init__(self, cors_options: Mapping[str, aiohttp_cors.ResourceOptions]):
        self._plugins = []
        self._initialized = False
        self.cors_options = cors_options
        self.webapps = []

    def add_plugin(self, plugin_mod: ModuleType):
        self._plugins.append(plugin_mod)

    async def init(self):
        if self._initialized:
            raise RuntimeError('already initialized')
        # TODO: Populate config from etcd
        config = {}
        for plugin_mod in self._plugins:
            try:
                subapp, global_middlewares = await plugin_mod.init(config, self.cors_options)
            except ValueError:
                raise RuntimeError('Webapp plugin protocol error: plugin.init() must return '
                                   '3-tuple of prefix, subapp, and global_middlewares')
            if not isinstance(subapp, web.Application):
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected aiohttp.web.Application instance for '
                                   '2nd return value of plugin.init()')
            if 'prefix' not in subapp or not subapp['prefix']:
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected aiohttp.web.Application instance '
                                   'to have the "prefix" key for URL routing')
            if global_middlewares is not None and not isinstance(subapp, Iterable):
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected None or an iterable of aiohttp.web middleware function for '
                                   '3rd return value of plugin.init()')
            self.webapps.append((subapp, global_middlewares))
        self._initialized = True

    async def shutdown(self):
        pass

    def enumerate_apps(self) -> Iterable[Tuple[web.Application, Iterable[WebMiddleware]]]:
        if not self._initialized:
            raise RuntimeError('Webapp plugins are not initialized yet.')
        yield from self.webapps


class HookPluginContext:

    _plugins: List[ModuleType]
    _hooks: List[AbstractHook]
    _handler_map: Mapping[HookEventTypes, Sequence[Callable[[Any], Awaitable[HookResult]]]]
    _initialized: bool

    def __init__(self):
        self._plugins = []
        self._hooks = []
        self._handler_map = defaultdict(list)
        self._initialized = False

    def add_plugin(self, plugin_mod: ModuleType):
        self._plugins.append(plugin_mod)

    async def init(self):
        if self._initialized:
            raise RuntimeError('already initialized')
        # TODO: Populate config from etcd
        config = {}
        for plugin_mod in self._plugins:
            hook = await plugin_mod.init(config)
            await hook.init()
            for event_type, handler in hook.get_handlers():
                self._handler_map[event_type].append(handler)
            self._hooks.append(hook)
        self._initialized = True

    async def shutdown(self):
        if not self._initialized:
            return
        await asyncio.gather(*[hook.shutdown() for hook in self._hooks])

    async def dispatch_event(self, event_type: HookEventTypes, event_arg: Any) -> HookResult:
        handlers = self._handler_map.get(event_type, [])
        results = await asyncio.gather(*[
            handler(event_arg)
            for handler in handlers
        ], return_exceptions=True)
        # We assume that exception logging is already done by plugins.
        if any(map(lambda r: isinstance(r, Exception) or r == HookResult.REJECTED, results)):
            return HookResult.REJECTED
        return HookResult.BYPASS
