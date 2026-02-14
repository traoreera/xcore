from xcore.configurations import core
from xcore.hooks import HookManager

xcfg = core.Xcorecfg(conf=core.Configure())

# Global hook manager instance
xhooks = HookManager()