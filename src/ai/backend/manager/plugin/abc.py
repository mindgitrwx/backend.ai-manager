from abc import ABCMeta, abstractmethod
from typing import Any, Awaitable, Callable, Iterable, Tuple

from .types import HookEventTypes, HookResult


class AbstractHook(metaclass=ABCMeta):

    @abstractmethod
    def get_handlers(self) -> Iterable[Tuple[HookEventTypes,
                                             Callable[[Any], Awaitable[HookResult]]]]:
        '''
        Return the list of events to hook.
        '''
        return []

    @abstractmethod
    async def init(self) -> None:
        '''
        Called after the agent is initialized.
        '''
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        '''
        Called when the agent is going to be terminated.
        '''
        pass
