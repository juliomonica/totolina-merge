"""Explicit Windows migration. Never mutate legacy storage or disclose payloads."""
from contextlib import ExitStack
from . import authentication as auth

ACTION = 'python tools/lunitora_setup.py --migrate-photoshop-auth'
FILENAME = auth.CAPABILITIES['photoshop']


def _source(root, security, photoshop, runner, stack):
    auth._guard_storage(root, FILENAME, runner, auth.STORAGE)
    local = auth._pin_ancestors(root, stack, security)
    directory = security.pin(stack, local, directory=True)
    token = security.pin(stack, local / FILENAME, directory=False)
    records = []
    for handle in (directory, token):
        snapshot = security.protection_snapshot(handle)
        if not security.reviewed_owner(snapshot):
            raise auth.AuthenticationError()
        info = security._FILE.GetFileInformationByHandle(handle)
        records.append((info[:2] + info[3:], snapshot))
    payload = security.read_storage(token)
    auth._validate_photoshop(payload, photoshop)
    return (tuple(records), payload), token


def _destination(root, security, photoshop, runner, stack):
    auth._guard_storage(root, FILENAME, runner, auth.PHOTOSHOP_STORAGE)
    path = auth._pin_ancestors(root, stack, security, auth.PHOTOSHOP_STORAGE)
    try:
        directory = security.pin(stack, path, directory=True)
    except Exception as error:
        if auth._missing(error): return None, None
        raise
    security.validate_acl(directory)
    if any(child.name != FILENAME for child in path.iterdir()):
        raise auth.AuthenticationError()
    try:
        token = security.pin(stack, path / FILENAME, directory=False)
    except Exception as error:
        if auth._missing(error): return (security._FILE.GetFileInformationByHandle(directory), None), None
        raise
    security.validate_acl(token)
    payload = security.read_storage(token)
    auth._validate_photoshop(payload, photoshop)
    return (security._FILE.GetFileInformationByHandle(directory),
            security._FILE.GetFileInformationByHandle(token)), payload


def migration_available(root, security, photoshop, runner):
    try:
        with ExitStack() as stack:
            _source(root, security, photoshop, runner, stack)
            evidence, payload = _destination(root, security, photoshop, runner, stack)
            return payload is None
    except Exception:
        return False


def migrate(root, platform_name, *, prompt=input, emit=print, runner=auth.run):
    if platform_name != 'windows':
        emit('REQUIRES MAC: native macOS credential protection is separate; no migration performed.')
        return 1
    try:
        _, security, photoshop = auth._reviewed_modules()
        with ExitStack() as stack:
            expected, _ = _source(root, security, photoshop, runner, stack)
            destination, payload = _destination(root, security, photoshop, runner, stack)
        if payload is not None:
            if payload != expected[1]: raise auth.AuthenticationError()
            emit('Destination already valid and byte-identical; no changes.')
            emit('legacy credential remains; cleanup available after live pairing acceptance')
            return 0
        emit('Legacy source is valid and identity-safe; credential value withheld.')
        emit('Copy existing bytes to ' + str(root / auth.PHOTOSHOP_STORAGE / FILENAME))
        emit('Create only the dedicated destination with current-user ownership and protected current-user/SYSTEM full-access DACLs. Leave legacy source and unrelated children untouched. Reopen and verify identity, ACL and exact byte equality; no rotation.')
        try:
            consent = prompt('Migrate this credential? [y/N]: ').strip().lower() == 'y'
        except (Exception, KeyboardInterrupt):
            consent = False
        if not consent:
            emit('Migration cancelled; no changes.')
            return 1
        with ExitStack() as stack:
            current, source = _source(root, security, photoshop, runner, stack)
            observed, payload = _destination(root, security, photoshop, runner, stack)
            if current != expected or observed != destination or payload is not None:
                raise auth.AuthenticationError()
            auth._guard_storage(root, FILENAME, runner, auth.PHOTOSHOP_STORAGE)
            path = root / auth.PHOTOSHOP_STORAGE
            if destination is None:
                security._FILE.CreateDirectory(str(path), security.protected_attributes(directory=True))
            directory = security.pin(stack, path, directory=True)
            security.validate_acl(directory)
            directory_identity = security._FILE.GetFileInformationByHandle(directory)[4:]
            if list(path.iterdir()): raise auth.AuthenticationError()
            token = security.pin(stack, path / FILENAME, directory=False, create=True)
            security.validate_acl(token)
            token_identity = security._FILE.GetFileInformationByHandle(token)[4:]
            security.write_storage(token, expected[1])
            token.Close()
            reopened = security.pin(stack, path / FILENAME, directory=False)
            security.validate_acl(reopened)
            # Size changes after writing; volume and file index must remain pinned.
            info = security._FILE.GetFileInformationByHandle(reopened)[4:]
            if (info[0], info[-2:]) != (token_identity[0], token_identity[-2:]):
                raise auth.AuthenticationError()
            if security._FILE.GetFileInformationByHandle(directory)[4:] != directory_identity:
                raise auth.AuthenticationError()
            if security.read_storage(reopened) != expected[1] or security.read_storage(source) != expected[1]:
                raise auth.AuthenticationError()
            reopened_directory = security.pin(stack, path, directory=True)
            security.validate_acl(reopened_directory)
            if security._FILE.GetFileInformationByHandle(reopened_directory)[4:] != directory_identity:
                raise auth.AuthenticationError()
            if sorted(child.name for child in path.iterdir()) != [FILENAME]:
                raise auth.AuthenticationError()
            auth._validate_photoshop(security.read_storage(reopened), photoshop)
            final_source, _ = _source(root, security, photoshop, runner, stack)
            # Creating the dedicated child changes the legacy directory write
            # time. Its identity/ACL and the entire source file record stay fixed.
            before_directory, before_acl = expected[0][0]
            after_directory, after_acl = final_source[0][0]
            if (before_directory[:2] + before_directory[3:] != after_directory[:2] + after_directory[3:]
                    or before_acl != after_acl
                    or final_source[0][1] != expected[0][1]
                    or final_source[1] != expected[1]):
                raise auth.AuthenticationError()
            security.validate_acl(reopened)
            auth._guard_storage(root, FILENAME, runner, auth.PHOTOSHOP_STORAGE)
        emit('Migration verified: destination protection and byte-identical credential; live authentication unverified.')
        emit('legacy credential remains; cleanup available after live pairing acceptance')
        return 0
    except Exception:
        emit('Migration blocked: unsafe, malformed, conflicting or concurrently changed storage, or unavailable Windows rights. Legacy source untouched; inspect destination before retry. Credential values withheld.')
        return 1
