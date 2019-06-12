from abc import ABCMeta, abstractmethod
from typing import Any

from .types import HookEventTypes


class AbstractHook(metaclass=ABCMeta):

    @abstractmethod
    async def init(self):
        '''
        Called after the agent is initialized.
        '''
        pass

    @abstractmethod
    async def shutdown(self):
        '''
        Called when the agent is going to be terminated.
        '''
        pass

    @abstractmethod
    async def handle_event(self, event_type: HookEventTypes, event_args: Any):
        '''
        The main method to implement.
        '''
        raise NotImplementedError
