"""BACnet enumerations and property tables (ASHRAE 135)."""

from __future__ import annotations


# ════════════════════════════════════════════════════════════════════════════
#  BACnet constants
# ════════════════════════════════════════════════════════════════════════════

AI, AO, AV, BI, BO, BV, DEVICE, MSI, MSO, MSV = 0, 1, 2, 3, 4, 5, 8, 13, 14, 19
OBJ_SHORT = {AI: "AI", AO: "AO", AV: "AV", BI: "BI", BO: "BO", BV: "BV",
             DEVICE: "DEV", MSI: "MSI", MSO: "MSO", MSV: "MSV"}
ANALOG = {AI, AO, AV}
BINARY = {BI, BO, BV}
MULTI = {MSI, MSO, MSV}
COMMANDABLE = {AO, AV, BO, BV, MSO, MSV}
POINT_TYPES = [AI, AO, AV, BI, BO, BV, MSI, MSV]
WILDCARD_INSTANCE = 4194303

# Property identifiers
P_ACTIVE_TEXT = 4
P_ALL = 8
P_APDU_TIMEOUT = 11
P_APP_SW_VERSION = 12
P_COV_INCREMENT = 22
P_DESCRIPTION = 28
P_DEVICE_ADDRESS_BINDING = 30
P_EVENT_STATE = 36
P_FIRMWARE_REV = 44
P_INACTIVE_TEXT = 46
P_LOCAL_DATE = 56
P_LOCAL_TIME = 57
P_LOCATION = 58
P_MAX_APDU = 62
P_MODEL_NAME = 70
P_NUM_APDU_RETRIES = 73
P_NUM_STATES = 74
P_OBJECT_ID = 75
P_OBJECT_LIST = 76
P_OBJECT_NAME = 77
P_OBJECT_TYPE = 79
P_OPTIONAL = 80
P_OUT_OF_SERVICE = 81
P_POLARITY = 84
P_PRESENT_VALUE = 85
P_PRIORITY_ARRAY = 87
P_PROTO_OBJ_TYPES = 96
P_PROTO_SERVICES = 97
P_PROTO_VERSION = 98
P_RELIABILITY = 103
P_RELINQUISH_DEFAULT = 104
P_REQUIRED = 105
P_SEGMENTATION = 107
P_STATE_TEXT = 110
P_STATUS_FLAGS = 111
P_SYSTEM_STATUS = 112
P_UNITS = 117
P_UTC_OFFSET = 119
P_VENDOR_ID = 120
P_VENDOR_NAME = 121
P_PROTO_REVISION = 139
P_DATABASE_REV = 155
P_MAX_SEGMENTS = 167
P_PROPERTY_LIST = 371

PROP_NAMES = {
    P_ACTIVE_TEXT: "activeText", P_ALL: "all", P_APDU_TIMEOUT: "apduTimeout",
    P_APP_SW_VERSION: "applicationSoftwareVersion", P_COV_INCREMENT: "covIncrement",
    P_DESCRIPTION: "description", P_DEVICE_ADDRESS_BINDING: "deviceAddressBinding",
    P_EVENT_STATE: "eventState", P_FIRMWARE_REV: "firmwareRevision",
    P_INACTIVE_TEXT: "inactiveText", P_LOCAL_DATE: "localDate", P_LOCAL_TIME: "localTime",
    P_LOCATION: "location", P_MAX_APDU: "maxApduLengthAccepted", P_MODEL_NAME: "modelName",
    P_NUM_APDU_RETRIES: "numberOfApduRetries", P_NUM_STATES: "numberOfStates",
    P_OBJECT_ID: "objectIdentifier", P_OBJECT_LIST: "objectList", P_OBJECT_NAME: "objectName",
    P_OBJECT_TYPE: "objectType", P_OPTIONAL: "optional", P_OUT_OF_SERVICE: "outOfService",
    P_POLARITY: "polarity", P_PRESENT_VALUE: "presentValue", P_PRIORITY_ARRAY: "priorityArray",
    P_PROTO_OBJ_TYPES: "protocolObjectTypesSupported", P_PROTO_SERVICES: "protocolServicesSupported",
    P_PROTO_VERSION: "protocolVersion", P_RELIABILITY: "reliability",
    P_RELINQUISH_DEFAULT: "relinquishDefault", P_REQUIRED: "required",
    P_SEGMENTATION: "segmentationSupported", P_STATE_TEXT: "stateText",
    P_STATUS_FLAGS: "statusFlags", P_SYSTEM_STATUS: "systemStatus", P_UNITS: "units",
    P_UTC_OFFSET: "utcOffset", P_VENDOR_ID: "vendorIdentifier", P_VENDOR_NAME: "vendorName",
    P_PROTO_REVISION: "protocolRevision", P_DATABASE_REV: "databaseRevision",
    P_MAX_SEGMENTS: "maxSegmentsAccepted", P_PROPERTY_LIST: "propertyList",
}

_COMMON = [P_PRESENT_VALUE, P_DESCRIPTION, P_STATUS_FLAGS, P_EVENT_STATE, P_RELIABILITY, P_OUT_OF_SERVICE]
_CMD = [P_PRIORITY_ARRAY, P_RELINQUISH_DEFAULT]
OBJECT_PROPS = {
    AI: _COMMON + [P_UNITS, P_COV_INCREMENT],
    AO: _COMMON + [P_UNITS] + _CMD + [P_COV_INCREMENT],
    AV: _COMMON + [P_UNITS] + _CMD + [P_COV_INCREMENT],
    BI: _COMMON + [P_POLARITY, P_INACTIVE_TEXT, P_ACTIVE_TEXT],
    BO: _COMMON + [P_POLARITY, P_INACTIVE_TEXT, P_ACTIVE_TEXT] + _CMD,
    BV: _COMMON + [P_INACTIVE_TEXT, P_ACTIVE_TEXT] + _CMD,
    MSI: _COMMON + [P_NUM_STATES, P_STATE_TEXT],
    MSO: _COMMON + [P_NUM_STATES, P_STATE_TEXT] + _CMD,
    MSV: _COMMON + [P_NUM_STATES, P_STATE_TEXT] + _CMD,
}
DEVICE_PROPS = [
    P_SYSTEM_STATUS, P_VENDOR_NAME, P_VENDOR_ID, P_MODEL_NAME, P_FIRMWARE_REV,
    P_APP_SW_VERSION, P_LOCATION, P_DESCRIPTION, P_PROTO_VERSION, P_PROTO_REVISION,
    P_PROTO_SERVICES, P_PROTO_OBJ_TYPES, P_OBJECT_LIST, P_MAX_APDU, P_SEGMENTATION,
    P_APDU_TIMEOUT, P_NUM_APDU_RETRIES, P_DEVICE_ADDRESS_BINDING, P_DATABASE_REV,
    P_LOCAL_DATE, P_LOCAL_TIME, P_UTC_OFFSET,
]
OPTIONAL_PROPS = {P_DESCRIPTION, P_RELIABILITY, P_COV_INCREMENT, P_LOCATION, P_LOCAL_DATE,
                  P_LOCAL_TIME, P_UTC_OFFSET, P_ACTIVE_TEXT, P_INACTIVE_TEXT, P_STATE_TEXT}
ARRAY_PROPS = {P_OBJECT_LIST, P_PRIORITY_ARRAY, P_STATE_TEXT, P_PROPERTY_LIST}

# PDU types
PDU_CONF, PDU_UNCONF, PDU_SACK, PDU_CACK, PDU_SEGACK, PDU_ERROR, PDU_REJECT, PDU_ABORT = range(8)

# Confirmed services
SC_COV_NOTIFY = 1
SC_SUBSCRIBE_COV = 5
SC_READ_PROP = 12
SC_READ_PROP_MULTI = 14
SC_WRITE_PROP = 15
SC_WRITE_PROP_MULTI = 16
SC_DCC = 17
SC_REINIT = 20
CONF_SERVICE_NAMES = {
    0: "AcknowledgeAlarm", 1: "ConfirmedCOVNotification", 2: "ConfirmedEventNotification",
    3: "GetAlarmSummary", 4: "GetEnrollmentSummary", 5: "SubscribeCOV", 6: "AtomicReadFile",
    7: "AtomicWriteFile", 8: "AddListElement", 9: "RemoveListElement", 10: "CreateObject",
    11: "DeleteObject", 12: "ReadProperty", 14: "ReadPropertyMultiple", 15: "WriteProperty",
    16: "WritePropertyMultiple", 17: "DeviceCommunicationControl", 18: "ConfirmedPrivateTransfer",
    20: "ReinitializeDevice", 26: "ReadRange", 28: "SubscribeCOVProperty", 29: "GetEventInformation",
}
# Unconfirmed services
SU_I_AM, SU_I_HAVE, SU_COV_NOTIFY = 0, 1, 2
SU_TIME_SYNC, SU_WHO_HAS, SU_WHO_IS, SU_UTC_TIME_SYNC = 6, 7, 8, 9
UNCONF_SERVICE_NAMES = {0: "I-Am", 1: "I-Have", 2: "UnconfirmedCOVNotification",
                        3: "UnconfirmedEventNotification", 4: "UnconfirmedPrivateTransfer",
                        6: "TimeSynchronization", 7: "Who-Has", 8: "Who-Is", 9: "UTCTimeSynchronization"}

# Error classes / codes
EC_DEVICE, EC_OBJECT, EC_PROPERTY, EC_RESOURCES, EC_SECURITY, EC_SERVICES = 0, 1, 2, 3, 4, 5
E_OTHER = 0
E_INCONSISTENT_PARAMS = 7
E_INVALID_DATATYPE = 9
E_NO_SPACE_LIST = 19
E_SERVICE_DENIED = 29
E_UNKNOWN_OBJECT = 31
E_UNKNOWN_PROPERTY = 32
E_VALUE_RANGE = 37
E_WRITE_DENIED = 40
E_INVALID_INDEX = 42
E_OPTIONAL_NOT_SUPPORTED = 45
E_NOT_ARRAY = 50
ERROR_NAMES = {E_OTHER: "other", E_INCONSISTENT_PARAMS: "inconsistent-parameters",
               E_INVALID_DATATYPE: "invalid-data-type", E_NO_SPACE_LIST: "no-space-to-add-list-element",
               E_SERVICE_DENIED: "service-request-denied", E_UNKNOWN_OBJECT: "unknown-object",
               E_UNKNOWN_PROPERTY: "unknown-property", E_VALUE_RANGE: "value-out-of-range",
               E_WRITE_DENIED: "write-access-denied", E_INVALID_INDEX: "invalid-array-index",
               E_OPTIONAL_NOT_SUPPORTED: "optional-functionality-not-supported",
               E_NOT_ARRAY: "property-is-not-an-array"}
ERROR_CLASS_NAMES = {0: "device", 1: "object", 2: "property", 3: "resources", 4: "security",
                     5: "services", 6: "vt", 7: "communication"}

# Reject / abort reasons
R_OTHER, R_INVALID_TAG, R_MISSING, R_RANGE, R_TOO_MANY, R_UNRECOGNIZED = 0, 4, 5, 6, 7, 9
REJECT_NAMES = {0: "other", 1: "buffer-overflow", 2: "inconsistent-parameters",
                3: "invalid-parameter-data-type", 4: "invalid-tag", 5: "missing-required-parameter",
                6: "parameter-out-of-range", 7: "too-many-arguments", 8: "undefined-enumeration",
                9: "unrecognized-service"}
A_OTHER, A_SEG_NOT_SUPPORTED, A_APDU_TOO_LONG = 0, 4, 11

# Network layer messages
NL_WHO_IS_ROUTER, NL_I_AM_ROUTER, NL_I_COULD_BE_ROUTER, NL_REJECT = 0x00, 0x01, 0x02, 0x03
NL_ROUTER_BUSY, NL_ROUTER_AVAILABLE, NL_INIT_RT, NL_INIT_RT_ACK = 0x04, 0x05, 0x06, 0x07
NL_NAMES = {0: "Who-Is-Router-To-Network", 1: "I-Am-Router-To-Network", 2: "I-Could-Be-Router-To-Network",
            3: "Reject-Message-To-Network", 4: "Router-Busy-To-Network", 5: "Router-Available-To-Network",
            6: "Initialize-Routing-Table", 7: "Initialize-Routing-Table-Ack",
            8: "Establish-Connection-To-Network", 9: "Disconnect-Connection-To-Network",
            0x12: "What-Is-Network-Number", 0x13: "Network-Number-Is"}

# BVLL functions (Annex J)
BVLC_RESULT, BVLC_WRITE_BDT, BVLC_READ_BDT, BVLC_READ_BDT_ACK = 0x00, 0x01, 0x02, 0x03
BVLC_FORWARDED, BVLC_REGISTER_FD, BVLC_READ_FDT, BVLC_READ_FDT_ACK = 0x04, 0x05, 0x06, 0x07
BVLC_DELETE_FDT, BVLC_DISTRIBUTE, BVLC_UNICAST, BVLC_BROADCAST = 0x08, 0x09, 0x0A, 0x0B

MAX_APDU_SIZES = [50, 128, 206, 480, 1024, 1476]
MAX_SEGS = {0: None, 1: 2, 2: 4, 3: 8, 4: 16, 5: 32, 6: 64, 7: None}

UNITS = {62: "°C", 64: "°F", 98: "%", 29: "%RH", 53: "Pa", 54: "kPa", 96: "ppm", 48: "kW",
         19: "kWh", 135: "m³/h", 87: "L/s", 27: "Hz", 5: "V", 3: "A", 95: ""}

DEVICE_SERVICE_BITS = (12, 14, 15, 16, 17, 20, 26, 27, 32, 33, 34, 36)


def max_apdu_from_code(code):
    return MAX_APDU_SIZES[code] if code < len(MAX_APDU_SIZES) else 1476


def max_apdu_to_code(size):
    best = 0
    for i, v in enumerate(MAX_APDU_SIZES):
        if v <= size:
            best = i
    return best
