# Parcel rerouting

`parcelbox.reroute(parcel_id, destination)` changes the destination of a parcel that has not been dispatched and returns the new destination. The change must remain visible through `parcelbox.destination(parcel_id)` after the service is reopened on the same path.

A dispatched parcel cannot be rerouted. Attempting it raises `parcelbox.ParcelDispatchedError` and leaves its destination unchanged.

Attempting to reroute an unknown parcel raises `parcelbox.UnknownParcelError`.
