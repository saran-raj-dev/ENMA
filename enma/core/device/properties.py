"""Object model of a device: resolving objects, reading and writing properties."""

from __future__ import annotations

import math
import time
from datetime import datetime

from enma.bacnet.codec import (
    BacErr,
    app_bits,
    app_bool,
    app_date,
    app_enum,
    app_null,
    app_oid,
    app_real,
    app_sint,
    app_str,
    app_time,
    app_uint,
    dec_app,
)
from enma.bacnet.constants import (
    ANALOG,
    ARRAY_PROPS,
    BINARY,
    DEVICE,
    DEVICE_PROPS,
    DEVICE_SERVICE_BITS,
    EC_OBJECT,
    EC_PROPERTY,
    E_INVALID_DATATYPE,
    E_INVALID_INDEX,
    E_NOT_ARRAY,
    E_UNKNOWN_OBJECT,
    E_UNKNOWN_PROPERTY,
    E_VALUE_RANGE,
    E_WRITE_DENIED,
    MSO,
    OBJECT_PROPS,
    OBJ_SHORT,
    OPTIONAL_PROPS,
    POINT_TYPES,
    P_ACTIVE_TEXT,
    P_ALL,
    P_APDU_TIMEOUT,
    P_APP_SW_VERSION,
    P_COV_INCREMENT,
    P_DATABASE_REV,
    P_DESCRIPTION,
    P_DEVICE_ADDRESS_BINDING,
    P_EVENT_STATE,
    P_FIRMWARE_REV,
    P_INACTIVE_TEXT,
    P_LOCAL_DATE,
    P_LOCAL_TIME,
    P_LOCATION,
    P_MAX_APDU,
    P_MAX_SEGMENTS,
    P_MODEL_NAME,
    P_NUM_APDU_RETRIES,
    P_NUM_STATES,
    P_OBJECT_ID,
    P_OBJECT_LIST,
    P_OBJECT_NAME,
    P_OBJECT_TYPE,
    P_OUT_OF_SERVICE,
    P_POLARITY,
    P_PRESENT_VALUE,
    P_PRIORITY_ARRAY,
    P_PROPERTY_LIST,
    P_PROTO_OBJ_TYPES,
    P_PROTO_REVISION,
    P_PROTO_SERVICES,
    P_PROTO_VERSION,
    P_RELIABILITY,
    P_RELINQUISH_DEFAULT,
    P_REQUIRED,
    P_SEGMENTATION,
    P_STATE_TEXT,
    P_STATUS_FLAGS,
    P_SYSTEM_STATUS,
    P_UNITS,
    P_UTC_OFFSET,
    P_VENDOR_ID,
    P_VENDOR_NAME,
    WILDCARD_INSTANCE,
)
from enma.config import APP_VERSION


class PropertiesMixin:
    """Object model of a device: resolving objects, reading and writing properties."""

    def resolve(self, oid):
        t, i = oid
        if t == DEVICE and (i == self.instance or i == WILDCARD_INSTANCE):
            return self
        p = self.points.get(oid)
        if p is not None and not p.deleted:
            return p
        raise BacErr(EC_OBJECT, E_UNKNOWN_OBJECT)

    def obj_id(self, obj):
        return (DEVICE, self.instance) if obj is self else obj.key

    def prop_list(self, obj):
        if obj is self:
            props = list(DEVICE_PROPS)
            if self.segmentation:
                props.insert(props.index(P_SEGMENTATION) + 1, P_MAX_SEGMENTS)
            return props
        return OBJECT_PROPS[obj.otype]

    def expand(self, obj, which):
        props = self.prop_list(obj)
        if which == P_ALL:
            return [P_OBJECT_ID, P_OBJECT_NAME, P_OBJECT_TYPE] + props + [P_PROPERTY_LIST]
        if which == P_REQUIRED:
            return [P_OBJECT_ID, P_OBJECT_NAME, P_OBJECT_TYPE] + \
                   [p for p in props if p not in OPTIONAL_PROPS] + [P_PROPERTY_LIST]
        return [p for p in props if p in OPTIONAL_PROPS]

    @staticmethod
    def _array(items, idx):
        if idx is None:
            return b"".join(items)
        if idx == 0:
            return app_uint(len(items))
        if 1 <= idx <= len(items):
            return items[idx - 1]
        raise BacErr(EC_PROPERTY, E_INVALID_INDEX)

    def read_value(self, obj, pid, idx):
        props = self.prop_list(obj)
        if pid not in props and pid not in (P_OBJECT_ID, P_OBJECT_NAME, P_OBJECT_TYPE, P_PROPERTY_LIST):
            raise BacErr(EC_PROPERTY, E_UNKNOWN_PROPERTY)
        if idx is not None and pid not in ARRAY_PROPS:
            raise BacErr(EC_PROPERTY, E_NOT_ARRAY)
        if pid == P_PROPERTY_LIST:
            return self._array([app_enum(p) for p in props], idx)
        if obj is self:
            return self._read_device(pid, idx)
        p = obj
        if pid == P_OBJECT_ID:
            return app_oid(p.otype, p.inst)
        if pid == P_OBJECT_NAME:
            return app_str(p.name)
        if pid == P_OBJECT_TYPE:
            return app_enum(p.otype)
        if pid == P_PRESENT_VALUE:
            p.reads += 1
            return p.enc_value(p.pv())
        if pid == P_DESCRIPTION:
            return app_str(p.desc)
        if pid == P_STATUS_FLAGS:
            return p.status_flags()
        if pid == P_EVENT_STATE:
            return app_enum(0)
        if pid == P_RELIABILITY:
            return app_enum(7 if p.fault else 0)
        if pid == P_OUT_OF_SERVICE:
            return app_bool(p.oos)
        if pid == P_UNITS:
            return app_enum(p.units)
        if pid == P_COV_INCREMENT:
            return app_real(p.cov_inc)
        if pid == P_PRIORITY_ARRAY:
            return self._array([app_null() if v is None else p.enc_value(v) for v in p.prio], idx)
        if pid == P_RELINQUISH_DEFAULT:
            return p.enc_value(p.value)
        if pid == P_POLARITY:
            return app_enum(0)
        if pid == P_ACTIVE_TEXT:
            return app_str((p.texts or ["inactive", "active"])[1])
        if pid == P_INACTIVE_TEXT:
            return app_str((p.texts or ["inactive", "active"])[0])
        if pid == P_NUM_STATES:
            return app_uint(len(p.texts or []))
        if pid == P_STATE_TEXT:
            return self._array([app_str(s) for s in (p.texts or [])], idx)
        raise BacErr(EC_PROPERTY, E_UNKNOWN_PROPERTY)

    def _read_device(self, pid, idx):
        if pid == P_OBJECT_ID:
            return app_oid(DEVICE, self.instance)
        if pid == P_OBJECT_NAME:
            return app_str(self.name)
        if pid == P_OBJECT_TYPE:
            return app_enum(DEVICE)
        if pid == P_SYSTEM_STATUS:
            return app_enum(0)
        if pid == P_VENDOR_NAME:
            return app_str(self.vendor_name)
        if pid == P_VENDOR_ID:
            return app_uint(self.vendor_id)
        if pid == P_MODEL_NAME:
            return app_str(self.model)
        if pid == P_FIRMWARE_REV:
            return app_str(self.firmware)
        if pid == P_APP_SW_VERSION:
            return app_str(f"enma-{APP_VERSION}")
        if pid == P_LOCATION:
            return app_str(self.location)
        if pid == P_DESCRIPTION:
            return app_str(self.description)
        if pid == P_PROTO_VERSION:
            return app_uint(1)
        if pid == P_PROTO_REVISION:
            return app_uint(14)
        if pid == P_PROTO_SERVICES:
            bits = [False] * 41
            for b in DEVICE_SERVICE_BITS:
                bits[b] = True
            bits[5] = self.cov_mode != "none"
            return app_bits(bits)
        if pid == P_PROTO_OBJ_TYPES:
            bits = [False] * 60
            for t in POINT_TYPES + [DEVICE, MSO]:
                bits[t] = True
            return app_bits(bits)
        if pid == P_OBJECT_LIST:
            if idx is None:
                return app_oid(DEVICE, self.instance) + b"".join(app_oid(*k) for k in self.order
                                                                  if not self.points[k].deleted)
            live = [k for k in self.order if not self.points[k].deleted]
            if idx == 0:
                return app_uint(len(live) + 1)
            if idx == 1:
                return app_oid(DEVICE, self.instance)
            if 2 <= idx <= len(live) + 1:
                return app_oid(*live[idx - 2])
            raise BacErr(EC_PROPERTY, E_INVALID_INDEX)
        if pid == P_MAX_APDU:
            return app_uint(self.max_apdu)
        if pid == P_SEGMENTATION:
            return app_enum(1 if self.segmentation else 3)
        if pid == P_MAX_SEGMENTS:
            return app_uint(1)
        if pid == P_APDU_TIMEOUT:
            return app_uint(3000)
        if pid == P_NUM_APDU_RETRIES:
            return app_uint(3)
        if pid == P_DEVICE_ADDRESS_BINDING:
            return b""
        if pid == P_DATABASE_REV:
            return app_uint(self.db_rev)
        if pid == P_LOCAL_DATE:
            return app_date(datetime.now())
        if pid == P_LOCAL_TIME:
            return app_time(datetime.now())
        if pid == P_UTC_OFFSET:
            off = -(time.altzone if time.daylight and time.localtime().tm_isdst else time.timezone) // 60
            return app_sint(-off)
        raise BacErr(EC_PROPERTY, E_UNKNOWN_PROPERTY)

    def _coerce(self, p, tag):
        if tag.kind != "app":
            raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
        typ, v = dec_app(tag)
        if p.otype in ANALOG:
            if typ != "real":
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            if math.isnan(v) or math.isinf(v):
                raise BacErr(EC_PROPERTY, E_VALUE_RANGE)
            return round(v, 4)
        if p.otype in BINARY:
            if typ != "enum":
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            if v not in (0, 1):
                raise BacErr(EC_PROPERTY, E_VALUE_RANGE)
            return v
        if typ != "uint":
            raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
        if not 1 <= v <= len(p.texts or []):
            raise BacErr(EC_PROPERTY, E_VALUE_RANGE)
        return v

    def write_value(self, obj, pid, idx, vals, prio):
        if not vals:
            raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
        v = vals[0]
        if obj is self:
            if pid in (P_LOCATION, P_DESCRIPTION):
                if v.kind != "app" or v.num != 7:
                    raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
                text = dec_app(v)[1]
                if pid == P_LOCATION:
                    self.location = text
                else:
                    self.description = text
                return
            if pid in self.prop_list(self) or pid in (P_OBJECT_ID, P_OBJECT_NAME, P_OBJECT_TYPE, P_PROPERTY_LIST):
                raise BacErr(EC_PROPERTY, E_WRITE_DENIED)
            raise BacErr(EC_PROPERTY, E_UNKNOWN_PROPERTY)
        p = obj
        props = self.prop_list(p)
        if pid not in props and pid not in (P_OBJECT_ID, P_OBJECT_NAME, P_OBJECT_TYPE, P_PROPERTY_LIST):
            raise BacErr(EC_PROPERTY, E_UNKNOWN_PROPERTY)
        if idx is not None and pid not in ARRAY_PROPS:
            raise BacErr(EC_PROPERTY, E_NOT_ARRAY)
        before = p.pv()
        if pid == P_PRESENT_VALUE:
            is_null = v.kind == "app" and v.num == 0
            if p.prio is not None:
                p.prio[prio - 1] = None if is_null else self._coerce(p, v)
            elif is_null:
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            elif p.oos:
                p.value = self._coerce(p, v)
            else:
                raise BacErr(EC_PROPERTY, E_WRITE_DENIED)
            self.sim.log(f"Device {self.instance}: {OBJ_SHORT[p.otype]}:{p.inst} presentValue "
                         f"{'relinquished' if is_null else 'written'} at priority {prio} → {p.value_text()}",
                         "write")
        elif pid == P_RELINQUISH_DEFAULT:
            p.value = self._coerce(p, v)
        elif pid == P_OUT_OF_SERVICE:
            if v.kind != "app" or v.num != 1:
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            old = p.oos
            p.oos = bool(v.lvt)
            if old != p.oos:
                self.on_value_changed(p, flags_changed=True)
            return
        elif pid == P_COV_INCREMENT:
            if v.kind != "app" or v.num != 4:
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            f = dec_app(v)[1]
            if f < 0 or math.isnan(f):
                raise BacErr(EC_PROPERTY, E_VALUE_RANGE)
            p.cov_inc = round(f, 4)
            return
        elif pid == P_DESCRIPTION:
            if v.kind != "app" or v.num != 7:
                raise BacErr(EC_PROPERTY, E_INVALID_DATATYPE)
            p.desc = dec_app(v)[1]
            return
        else:
            raise BacErr(EC_PROPERTY, E_WRITE_DENIED)
        if p.pv() != before:
            self.on_value_changed(p)
