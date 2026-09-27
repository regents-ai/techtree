The exported service reroutes an undispatched parcel, returns and reports its new destination, and preserves that destination after reopening the store.
The exported service rejects rerouting a dispatched parcel with ParcelDispatchedError and preserves its existing destination.
The exported service rejects rerouting an unknown parcel with UnknownParcelError.
The submitted tests fail when reroute leaves an undispatched parcel unchanged.
The submitted tests fail when reroute permits a dispatched parcel to change destination.
The submitted tests pass unchanged against a behavior-equivalent implementation with different private modules and storage.
