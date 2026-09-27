from . import _persistence, _routing


class UnknownParcelError(LookupError):
    pass


class ParcelDispatchedError(RuntimeError):
    pass


def open(path):
    _persistence.open_store(path)
    _routing.reset(_persistence.RECORDS)


def create_parcel(parcel_id, destination):
    record = {"destination": destination, "dispatched": False}
    _persistence.RECORDS[parcel_id] = record
    _routing.ROUTES[parcel_id] = destination
    _routing.DISPATCHED.discard(parcel_id)
    _persistence.save()
    return parcel_id


def dispatch(parcel_id):
    if parcel_id not in _persistence.RECORDS:
        raise UnknownParcelError(parcel_id)
    _persistence.RECORDS[parcel_id]["dispatched"] = True
    _routing.DISPATCHED.add(parcel_id)
    _persistence.save()


def destination(parcel_id):
    if parcel_id not in _persistence.RECORDS:
        raise UnknownParcelError(parcel_id)
    return _persistence.RECORDS[parcel_id]["destination"]


def reroute(parcel_id, destination):
    raise NotImplementedError("rerouting is not implemented")
