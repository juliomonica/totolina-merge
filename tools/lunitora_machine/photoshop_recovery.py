"""Explicit, token-preserving Windows protection recovery. No credential writers."""
from contextlib import ExitStack
from . import authentication as auth

ACTION = "python tools/lunitora_setup.py --repair-photoshop-auth"


def _evidence(root, security, photoshop, runner, stack, *, mutation=False, inspect_children=True):
    auth._guard_storage(root, auth.CAPABILITIES['photoshop'], runner)
    local = auth._pin_ancestors(root, stack, security, auth.storage_for(root, auth.CAPABILITIES["photoshop"]))
    children = [(child, child.is_dir()) for child in sorted(local.iterdir())]
    opener = security.repair_handle if mutation else security.pin
    directory = opener(stack, local, directory=True)
    token = opener(stack, local / auth.CAPABILITIES['photoshop'], directory=False)
    # Windows can propagate a changed directory DACL to unprotected children.
    # Never repair those unrelated objects. Pin every immediate child to prevent
    # concurrent changes and require an inheritance barrier before directory repair.
    child_records = []
    child_handles = []
    directory_unsafe = False
    try:
        security.validate_acl(directory)
    except Exception:
        directory_unsafe = True
    if directory_unsafe and inspect_children:
        for child, is_directory in children:
            if child.name == auth.CAPABILITIES['photoshop']:
                continue
            handle = security.pin_child_security(stack, child, directory=is_directory)
            snapshot = security.protection_snapshot(handle)
            if not snapshot[1] & 0x1000:
                raise DirectoryInheritanceError()
            child_records.append((child.name, security._FILE.GetFileInformationByHandle(handle)[4:], snapshot))
            child_handles.append(handle)
    records = []
    for handle in (directory, token):
        snapshot = security.protection_snapshot(handle)
        if not security.reviewed_owner(snapshot):
            raise auth.AuthenticationError()
        info = security._FILE.GetFileInformationByHandle(handle)
        # Reading can update last-access time; retain identity, size and write time.
        records.append((info[:2] + info[3:], snapshot))
    payload = security.read_storage(token)
    auth._validate_photoshop(payload, photoshop)
    problems = []
    for label, handle, (_, snapshot) in zip(('Directory', 'Token file'), (directory, token), records):
        try:
            security.validate_acl(handle)
        except Exception:
            user, _ = security._native().identity()
            reasons = []
            if snapshot[0] != user:
                reasons.append('owner is not the current Windows user')
            if not snapshot[1] & 0x1000:
                reasons.append('DACL inheritance is not protected')
            reasons.append('DACL must contain exactly current-user and SYSTEM explicit full-access allow entries')
            problems.append(label + ': ' + '; '.join(reasons))
    return (tuple(records), payload, tuple(child_records)), (directory, token, *child_handles), problems


class DirectoryInheritanceError(auth.AuthenticationError):
    pass


def repair_available(root, security, photoshop, runner):
    try:
        with ExitStack() as stack:
            _, _, problems = _evidence(root, security, photoshop, runner, stack, inspect_children=False)
        return bool(problems)
    except DirectoryInheritanceError:
        return True
    except Exception:
        return False


def repair(root, platform_name, *, prompt=input, emit=print, runner=auth.run):
    try:
        if platform_name != 'windows':
            raise auth.AuthenticationError()
        _, security, photoshop = auth._reviewed_modules()
        with ExitStack() as stack:
            expected, _, problems = _evidence(root, security, photoshop, runner, stack, inspect_children=False)
        if not problems:
            emit('Photoshop authentication storage is already protected; token preserved.')
            return 0
        emit('Photoshop authentication storage needs explicit protection repair')
        for problem in problems:
            emit(problem)
        with ExitStack() as stack:
            expected, _, _ = _evidence(root, security, photoshop, runner, stack)
        emit('Repair changes ownership/DACL only on ' + str(root / auth.storage_for(root, auth.CAPABILITIES['photoshop'])) + ' and pairing-token.txt. It does not propagate ACLs to unrelated children or change token bytes.')
        try:
            consent = prompt('Apply this protection repair? [y/N]: ').strip().lower() == 'y'
        except (Exception, KeyboardInterrupt):
            consent = False
        if not consent:
            emit('Photoshop protection repair cancelled; no changes.')
            return 1
        with ExitStack() as stack:
            current, handles, _ = _evidence(root, security, photoshop, runner, stack, mutation=True)
            if current != expected:
                raise auth.AuthenticationError()
            auth._guard_storage(root, auth.CAPABILITIES['photoshop'], runner)
            # Protect the token before changing its parent's inheritance policy.
            for index in (1, 0):
                handle = handles[index]
                if security.protection_snapshot(handle) != expected[0][index][1]:
                    raise auth.AuthenticationError()
                if security.read_storage(handles[1]) != expected[1]:
                    raise auth.AuthenticationError()
                try:
                    security.validate_acl(handle)
                except Exception:
                    security.apply_protection(handle, directory=index == 0)
            for handle in handles[:2]:
                security.validate_acl(handle)
            for handle, (_, identity, snapshot) in zip(handles[2:], expected[2]):
                if (security.protection_snapshot(handle) != snapshot
                        or security._FILE.GetFileInformationByHandle(handle)[4:] != identity):
                    raise auth.AuthenticationError()
            if security.read_storage(handles[1]) != expected[1]:
                raise auth.AuthenticationError()
        emit('Photoshop protection repair verified; existing token bytes preserved exactly. Live Art acceptance remains unverified.')
        return 0
    except DirectoryInheritanceError:
        emit('Photoshop protection repair blocked: repairing .local would change inherited ACLs on unrelated children. No changes were made. Run python tools/lunitora_setup.py --migrate-photoshop-auth.')
        return 1
    except Exception:
        emit('Photoshop protection repair blocked: unsafe/ambiguous provenance, changed state, concurrent access, or insufficient Windows security rights. No token was written. Any partial protection change requires another inspection.')
        return 1
