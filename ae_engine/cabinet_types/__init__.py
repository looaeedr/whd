from .registry import CabinetTypeRegistration, register_cabinet_type, registered_cabinet_types, resolve_cabinet_type
from .vault import REGISTRATION as VAULT_REGISTRATION
from .ro import REGISTRATION as RO_REGISTRATION
from .receiving import REGISTRATION as RECEIVING_REGISTRATION
register_cabinet_type(VAULT_REGISTRATION)
register_cabinet_type(RO_REGISTRATION)
register_cabinet_type(RECEIVING_REGISTRATION)
from . import policy as policy
__all__ = ["CabinetTypeRegistration", "register_cabinet_type", "registered_cabinet_types", "resolve_cabinet_type", "policy"]
