ROUTES = {}
DISPATCHED = set()


def reset(records):
    ROUTES.clear()
    DISPATCHED.clear()
    for parcel_id, record in records.items():
        ROUTES[parcel_id] = record["destination"]
        if record["dispatched"]:
            DISPATCHED.add(parcel_id)
