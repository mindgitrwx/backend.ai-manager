import enum


class HookEventTypes(enum.Enum):
    USER_SIGNUP = 0x1001
    USER_LOGIN = 0x1002
    KERNEL_START = 0x2001
    KERNEL_TERMINATE = 0x2002
    VFOLDER_CREATE = 0x3001
    VFOLDER_DELETE = 0x3002


class HookResult(enum.Enum):
    BYPASS = 0
    REJECTED = 1
    MODIFIED = 2
