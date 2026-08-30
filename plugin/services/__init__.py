"""Plugin services. Specification section 7.10.

Services are assembled once, during registration, into one immutable
container. No service constructor performs network, CLI, Docker, or model
work: building the container is pure bookkeeping over files that shipped with
the plugin.
"""
