"""Static guards for container-image package-manager invariants."""


def test_arch_family_images_do_not_perform_partial_upgrades(repo):
    """Refreshing pacman metadata without upgrading the base image can mix
    Python and Expat ABIs, making pyexpat fail before the suite reaches project
    code. Every Arch-family dependency install must be a full sync upgrade.
    """
    containers = repo / "tests/containers"
    for distro in ("arch", "cachyos", "endeavouros", "garuda", "manjaro"):
        text = (containers / f"Dockerfile.{distro}").read_text()
        assert "pacman -Syu --noconfirm --needed" in text, distro
        assert "pacman -Sy --noconfirm --needed" not in text, distro


def test_ci_targets_only_cachyos(repo):
    """Both the core suite and native probes use the daily-driver distro."""
    import re

    workflow = (repo / ".github/workflows/test.yml").read_text()
    jobs = workflow.split("jobs:\n", 1)[1]
    assert re.findall(r"(?m)^  ([a-z-]+):$", jobs) == ["test", "cachyos"]
    assert "container: cachyos/cachyos:latest" in jobs
    assert "-f tests/containers/Dockerfile.cachyos" in jobs
    assert "docker run --rm tajsdesktop-test-cachyos:ci" in jobs
    assert "matrix" not in jobs
    assert "continue-on-error" not in jobs


def test_ci_preserves_full_core_suite_and_cachyos_keyrings(repo):
    workflow = (repo / ".github/workflows/test.yml").read_text()
    assert "python -m pytest tests -q --ignore=tests/containers" in workflow
    assert "pacman-key --populate archlinux cachyos" in workflow
    assert "pacman -Sy --noconfirm archlinux-keyring cachyos-keyring" in workflow
    assert "pacman -Syu --noconfirm" in workflow
    assert 'exit ${exit_code:-0}' in workflow


def test_gentoo_base_build_is_manual_only(repo):
    workflow = (repo / ".github/workflows/build-gentoo-base.yml").read_text()
    triggers = workflow.split("\non:\n", 1)[1].split("\njobs:", 1)[0]
    assert triggers.strip() == "workflow_dispatch: {}"
