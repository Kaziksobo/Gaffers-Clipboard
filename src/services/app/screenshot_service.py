"""
ScreenshotService - timed screenshot capture and retention for OCR workflows.

This module defines ScreenshotService, a small UI-agnostic service that captures
screenshots with an optional delay, supports UI overlay and flush callbacks,
stores captures in the project screenshots directory, and cleans up older files
to keep disk usage bounded.

Responsibilities:
- Capture screenshots with configurable delay behavior.
- Expose retrieval of the latest OCR-ready screenshot path.
- Validate screenshot output existence and raise domain-specific errors.
- Prune old screenshots while retaining a recent history window.
- The service isolates screenshot lifecycle concerns from controllers and OCR logic.
"""

import logging
import time
from pathlib import Path

import pyautogui

from src.contracts.backend import OverlayCallback, UIFlushCallback
from src.exceptions import ScreenshotError

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Manage timed screenshot capture and lifecycle for OCR-ready images.

    Provides a thin abstraction over pyautogui that handles delays, overlay
    messaging, file management, and cleanup of older screenshots.

    """

    def __init__(
        self,
        project_root: Path,
        screenshot_delay: int = 3,
        overlay_callback: OverlayCallback | None = None,
        ui_flush_callback: UIFlushCallback | None = None,
    ) -> None:
        """Initialize the screenshot service with paths, timing, and UI hooks.

        Stores configuration for where screenshots are written, how long to
        delay before capture, and which callbacks to use for overlays and UI flushing.

        Args:
            project_root (Path): Root directory of the project used to derive the
                screenshots folder location.
            screenshot_delay (int, optional): Default number of seconds to wait
                before taking a screenshot. Defaults to 3.
            overlay_callback (OverlayCallback | None, optional): Optional
                function used to display a countdown or message overlay to the user.
            ui_flush_callback (UIFlushCallback | None, optional): Optional function
                invoked to flush pending UI events before blocking for the delay.

        Raises:
            OSError: If the screenshots directory cannot be created or accessed.
        """
        if screenshot_delay < 0:
            logger.warning(
                "Negative default screenshot_delay (%ss); using 0s.",
                screenshot_delay,
            )
            screenshot_delay = 0

        self._default_delay: int = screenshot_delay
        self._overlay_callback: OverlayCallback | None = overlay_callback
        self._ui_flush_callback: UIFlushCallback | None = ui_flush_callback
        self._project_root: Path = project_root
        self._screenshots_dir: Path = self._project_root / "screenshots"
        self._screenshots_dir.mkdir(parents=True, exist_ok=True)
        self._screenshot_path: Path | None = None

    def capture_screenshot(self, delay: int | None = None) -> None:
        """Capture a timed screenshot and persist it for downstream OCR use.

        Applies an optional delay with UI callbacks, writes the image to the
        screenshots directory, and prunes older captures to a fixed history.

        Args:
            delay (int | None, optional): Number of seconds to wait before
                capturing the screenshot. When None, uses the default delay
                configured on the service.

        Raises:
            ScreenshotError: If callbacks fail, screenshot capture fails,
                or the expected output file is not created.
        """
        if delay is None:
            delay = self._default_delay
        if delay < 0:
            logger.warning(
                "Negative delay (%ss), using default %ss.",
                delay,
                self._default_delay,
            )
            delay = self._default_delay

        logger.info("Initiating screenshot (delay: %ss)", delay)
        filename = f"stats_capture_{int(time.time())}.png"
        screenshot_path = self._screenshots_dir / filename

        try:
            self._run_pre_capture_delay(delay)

            pyautogui.screenshot(screenshot_path)
            logger.info("Screenshot saved: %s", screenshot_path)
            self._cleanup_screenshots()

            # Ensure the screenshot file is fully written and accessible.
            if not screenshot_path.exists():
                logger.error(
                    "Screenshot file not found after capture: %s",
                    screenshot_path,
                )
                raise ScreenshotError("Screenshot file was not created successfully.")

        except ScreenshotError:
            raise
        except Exception as e:
            logger.error("Screenshot capture workflow failed: %s", e, exc_info=True)
            raise ScreenshotError(f"Failed to capture screenshot: {e}") from e

        self._screenshot_path = screenshot_path

    def _run_pre_capture_delay(self, delay: int) -> None:
        """Execute optional pre-capture UI hooks and fallback delay behavior."""
        if self._ui_flush_callback:
            self._ui_flush_callback()

        if self._overlay_callback:
            self._overlay_callback(delay, "Switch to the game screen now")
            return

        logger.debug("No overlay callback provided, using time.sleep for delay.")
        time.sleep(delay)

    def get_latest_screenshot_path(self) -> Path:
        """Return the most recent OCR-ready screenshot path from disk.

        Validates the screenshots directory, selects the newest matching file,
        and surfaces missing-directory or no-file states as screenshot errors.

        Raises:
            ScreenshotError: If the screenshots directory is missing, unreadable,
                contains unreadable files, or has no matching screenshot files.

        Returns:
            Path: Filesystem path to the latest `stats_capture_*.png` screenshot.
        """
        if not self._screenshots_dir.exists():
            logger.error(
                "Screenshot lookup failed: Directory missing at %s",
                self._screenshots_dir,
            )
            raise ScreenshotError("Screenshots directory does not exist.")

        try:
            screenshot_files = list(self._screenshots_dir.glob("stats_capture_*.png"))
        except OSError as e:
            logger.error(
                "Screenshot lookup failed while scanning %s: %s",
                self._screenshots_dir,
                e,
                exc_info=True,
            )
            raise ScreenshotError("Failed to read screenshots directory.") from e

        if screenshot_files:
            try:
                latest_file = max(screenshot_files, key=lambda p: p.stat().st_mtime)
            except OSError as e:
                logger.error(
                    "Screenshot lookup failed while reading file metadata in %s: %s",
                    self._screenshots_dir,
                    e,
                    exc_info=True,
                )
                raise ScreenshotError("Failed to inspect screenshot files.") from e

            logger.info("Latest screenshot identified: %s", latest_file.name)
            return latest_file

        logger.error(
            "Screenshot lookup failed: No valid images found in %s",
            self._screenshots_dir,
        )
        raise ScreenshotError("No screenshots found in the screenshots directory.")

    def _cleanup_screenshots(self, max_files: int = 5) -> None:
        """Prune older screenshots to maintain a bounded history on disk.

        Keeps only the newest captures up to a configured limit and removes
        older files, logging any failures without interrupting the main flow.

        Args:
            max_files (int, optional): Maximum number of recent screenshot files
                to retain in the screenshots directory. Defaults to 5.
        """
        if not self._screenshots_dir.exists():
            return

        # Get all screenshot files
        try:
            screenshot_files = list(self._screenshots_dir.glob("stats_capture_*.png"))
        except OSError as e:
            logger.warning(
                "Cleanup skipped: failed to scan screenshots directory %s: %s",
                self._screenshots_dir,
                e,
            )
            return

        # Sort files by modification time (newest first), skipping unreadable files.
        sortable_files: list[tuple[float, Path]] = []
        for file_path in screenshot_files:
            try:
                sortable_files.append((file_path.stat().st_mtime, file_path))
            except OSError as e:
                logger.warning(
                    "Cleanup skipped unreadable screenshot %s: %s",
                    file_path,
                    e,
                )

        if not sortable_files:
            return

        sortable_files.sort(key=lambda item: item[0], reverse=True)
        sorted_paths = [path for _, path in sortable_files]

        # Identify files to delete (everything after the first max_files)
        files_to_delete = sorted_paths[max_files:]

        if not files_to_delete:
            return

        logger.info("Cleanup: Deleting %s old screenshots.", len(files_to_delete))
        for file_path in files_to_delete:
            try:
                file_path.unlink()
                logger.debug("Deleted old screenshot: %s", file_path)
            except Exception as e:
                logger.warning(
                    "Failed to delete screenshot %s. It may be in use: %s",
                    file_path,
                    e,
                )
