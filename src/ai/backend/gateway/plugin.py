from abc import ABCMeta, abstractmethod
import logging
import pkg_resources
from types import ModuleType
from typing import Callable, Iterable, Mapping, Tuple

from aiohttp import web
import aiohttp_cors

from ai.backend.common.logging import BraceStyleAdapter

log = BraceStyleAdapter(logging.getLogger('ai.backend.gateway.plugin'))

WebMiddleware = Callable[[web.Request, web.Response], None]


def load_webapp_plugins(cors_options: Mapping[str, aiohttp_cors.ResourceOptions]):
    entry_prefix = 'backendai_manager_webapp_v10'
    webapp_plugin_ctx = WebAppPluginContext(cors_options)
    for entrypoint in pkg_resources.iter_entry_points(entry_prefix):
        log.info('Loading webapp plugin from {}', entrypoint)
        webapp_plugin_ctx.add_plugin(entrypoint.load())
    return webapp_plugin_ctx


def load_hook_plugins():
    entry_prefix = 'backendai_manager_hooks_v10'
    hook_plugin_ctx = HookPluginContext()
    for entrypoint in pkg_resources.iter_entry_points(entry_prefix):
        log.info('Loading hook plugin from {}', entrypoint)
        hook_plugin_ctx.add_plugin(entrypoint.load())
    return hook_plugin_ctx


class AbstractHookPlugin(metaclass=ABCMeta):

    @abstractmethod
    def handle_event(self, event_type, event_args):
        raise NotImplementedError


class WebAppPluginContext:

    def __init__(self, cors_options: Mapping[str, aiohttp_cors.ResourceOptions]):
        self._plugins = []
        self._initialized = False
        self.cors_options = cors_options
        self.webapps = []

    async def init(self):
        for plugin_mod in self._plugins:
            try:
                prefix, subapp, global_middlewares = await plugin_mod.init(self.cors_options)
            except ValueError:
                raise RuntimeError('Webapp plugin protocol error: plugin.init() must return '
                                   '3-tuple of prefix, subapp, and global_middlewares')
            if not isinstance(prefix, str) or not prefix:
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected non-empty string for 1st return value of plugin.init()')
            if not isinstance(subapp, web.Application):
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected aiohttp.web.Application instance for '
                                   '2nd return value of plugin.init()')
            if global_middlewares is not None and not isinstance(subapp, Iterable):
                raise RuntimeError('Webapp plugin protocol error: '
                                   'expected None or an iterable of aiohttp.web middleware function for '
                                   '3rd return value of plugin.init()')
            self.webapps.append((prefix, subapp, global_middlewares))
        self._initialized = True

    async def shutdown(self):
        pass

    async def add_plugin(self, plugin_mod: ModuleType):
        self._plugins.append(plugin_mod)

    def enumerate_apps(self) -> Iterable[Tuple[str, web.Application, Iterable[WebMiddleware]]]:
        if not self._initialized:
            raise RuntimeError('Webapp plugins are not initialized yet.')
        yield from self.webapps


class HookPluginContext:

    async def init(self):
        pass

    async def shutdown(self):
        pass

    def dispatch_event(self, event_type, event_args):
        pass
