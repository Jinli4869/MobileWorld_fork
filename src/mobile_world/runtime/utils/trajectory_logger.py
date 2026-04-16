import json
import os
from datetime import datetime

from loguru import logger
from PIL import Image, ImageDraw

from mobile_world.runtime.protocol.events import CanonicalTrajectoryHeader
from mobile_world.runtime.protocol.normalization import normalize_score_event, normalize_step_event
from mobile_world.runtime.utils.models import Observation


def save_screenshot(screenshot, path) -> None:
    screenshot.save(path)
    logger.info(f"Screenshot saved in {path}")


def extract_click_coordinates(action):
    x = action.get("x")
    y = action.get("y")
    action_corr = (x, y)
    return action_corr


def extract_drag_coordinates(action):
    start_x = action.get("start_x")
    start_y = action.get("start_y")
    end_x = action.get("end_x")
    end_y = action.get("end_y")
    return (start_x, start_y, end_x, end_y)


# Function to draw points on an image
def draw_clicks_on_image(image_path, output_path, click_coords):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    # Draw each click coordinate as a red circle
    (x, y) = click_coords
    radius = 20
    if x and y:  # if get the coordinate, draw a circle
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="red", outline="red")

    # Save the modified image
    save_screenshot(image, output_path)


# Function to draw a drag line on an image
def draw_drag_on_image(image_path, output_path, drag_coords):
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)

    (start_x, start_y, end_x, end_y) = drag_coords
    if start_x and start_y and end_x and end_y:
        # Draw a line from start to end
        draw.line((start_x, start_y, end_x, end_y), fill="blue", width=5)
        # Draw circles at start (green) and end (red) points
        radius = 15
        draw.ellipse(
            (start_x - radius, start_y - radius, start_x + radius, start_y + radius),
            fill="green",
            outline="green",
        )
        draw.ellipse(
            (end_x - radius, end_y - radius, end_x + radius, end_y + radius),
            fill="red",
            outline="red",
        )

    # Save the modified image
    save_screenshot(image, output_path)


LOG_FILE_NAME = "traj.json"
CANONICAL_LOG_FILE_NAME = "traj.canonical.jsonl"
CANONICAL_META_FILE_NAME = "traj.meta.json"
SCORE_FILE_NAME = "result.txt"


class TrajLogger:
    def __init__(self, log_file_root: str, task_name: str):
        self.log_file_dir = os.path.join(log_file_root, task_name)
        self.log_file_name = LOG_FILE_NAME
        self.canonical_log_file_name = CANONICAL_LOG_FILE_NAME
        self.canonical_meta_file_name = CANONICAL_META_FILE_NAME
        self.score_file_name = SCORE_FILE_NAME
        self.screenshots_dir = "screenshots"
        self.marked_screenshots_dir = "marked_screenshots"
        self.tools = None

        if os.path.exists(self.log_file_dir) and os.path.exists(
            os.path.join(self.log_file_dir, self.screenshots_dir)
        ):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = f"{self.log_file_dir}_backup_{timestamp}"

            # Rename existing folder to backup
            os.rename(self.log_file_dir, backup_dir)
            logger.info(f"Existing folder renamed to: {backup_dir}")

        os.makedirs(self.log_file_dir, exist_ok=True)
        os.makedirs(os.path.join(self.log_file_dir, self.screenshots_dir), exist_ok=True)
        os.makedirs(os.path.join(self.log_file_dir, self.marked_screenshots_dir), exist_ok=True)
        with open(os.path.join(self.log_file_dir, self.log_file_name), "w") as f:
            json.dump({}, f)
        with open(os.path.join(self.log_file_dir, self.canonical_log_file_name), "w") as f:
            f.write("")
        with open(os.path.join(self.log_file_dir, self.canonical_meta_file_name), "w") as f:
            json.dump({}, f)

    def _canonical_paths(self) -> tuple[str, str]:
        return (
            os.path.join(self.log_file_dir, self.canonical_log_file_name),
            os.path.join(self.log_file_dir, self.canonical_meta_file_name),
        )

    @staticmethod
    def _read_json_or_default(path: str, default: dict | None = None) -> dict:
        if default is None:
            default = {}
        if not os.path.exists(path):
            return default.copy()
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return default.copy()

    def _write_canonical_meta(
        self,
        task_name: str,
        task_goal: str,
        task_id: str,
        token_usage: dict[str, int] | None = None,
    ) -> None:
        _, meta_path = self._canonical_paths()
        existing_meta = self._read_json_or_default(meta_path, default={})
        header = CanonicalTrajectoryHeader(
            task_name=task_name,
            task_goal=task_goal,
            run_id=f"{task_name}-{task_id}",
            tools=self.tools or [],
            metadata={"legacy_traj_file": self.log_file_name},
        ).model_dump()
        for key in ("tool_manifest", "policy_manifest", "token_usage"):
            if key in existing_meta:
                header[key] = existing_meta[key]
        if token_usage is not None:
            header["token_usage"] = token_usage
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(header, f, ensure_ascii=False, indent=4)

    def _append_canonical_event(self, event: dict) -> None:
        canonical_path, _ = self._canonical_paths()
        with open(canonical_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def log_traj(
        self,
        task_name: str,
        task_goal: str,
        step: int,
        prediction: str,
        action: dict,
        obs: Observation,
        token_usage: dict[str, int] = None,
    ) -> None:
        task_id = "0"

        with open(os.path.join(self.log_file_dir, self.log_file_name)) as f:
            log_data = json.load(f)

        if task_id not in log_data:
            log_data[task_id] = {"tools": self.tools, "traj": []}

        log_data[task_id]["traj"].append(
            {
                "task_goal": task_goal,
                "step": step,
                "prediction": prediction,
                "action": action,
                "ask_user_response": obs.ask_user_response,
                "tool_call": obs.tool_call,
            }
        )
        log_data[task_id]["token_usage"] = token_usage

        with open(os.path.join(self.log_file_dir, self.log_file_name), "w") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
        self._write_canonical_meta(task_name, task_goal, task_id, token_usage=token_usage)
        canonical_step = normalize_step_event(
            task_name=task_name,
            task_goal=task_goal,
            run_id=f"{task_name}-{task_id}",
            step=step,
            prediction=prediction,
            action=action,
            observation=obs,
            token_usage=token_usage,
        )
        self._append_canonical_event(canonical_step.model_dump())

        original_screenshot_path = os.path.join(
            self.log_file_dir, self.screenshots_dir, f"{task_name}-{task_id}-{step}.png"
        )
        save_screenshot(obs.screenshot, original_screenshot_path)

        action_type = action.get("action_type")
        if action_type in ["click", "double_tap", "long_press"]:
            click_coordinates = extract_click_coordinates(action)
            marked_screenshot_path = os.path.join(
                self.log_file_dir,
                self.marked_screenshots_dir,
                f"marked-{task_name}-{task_id}-{step}.png",
            )
            draw_clicks_on_image(
                original_screenshot_path, marked_screenshot_path, click_coordinates
            )
        elif action_type == "drag":
            drag_coordinates = extract_drag_coordinates(action)
            marked_screenshot_path = os.path.join(
                self.log_file_dir,
                self.marked_screenshots_dir,
                f"marked-{task_name}-{task_id}-{step}.png",
            )
            draw_drag_on_image(original_screenshot_path, marked_screenshot_path, drag_coordinates)

    def log_tools(self, tools: list[dict]):
        self.tools = tools
        _, meta_path = self._canonical_paths()
        meta = self._read_json_or_default(meta_path, default={})
        meta["tools"] = tools
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)

    def log_tool_manifest(self, manifest: dict) -> None:
        """Persist deterministic tool manifest to legacy and canonical artifacts."""
        task_id = "0"
        legacy_path = os.path.join(self.log_file_dir, self.log_file_name)
        legacy = self._read_json_or_default(legacy_path, default={})
        if task_id not in legacy:
            legacy[task_id] = {"tools": self.tools, "traj": []}
        legacy[task_id]["tool_manifest"] = manifest
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False, indent=4)

        _, meta_path = self._canonical_paths()
        meta = self._read_json_or_default(meta_path, default={})
        meta["tool_manifest"] = manifest
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=4)

    def log_tool_error(self, *, step: int, error: dict) -> None:
        """Attach normalized tool error to the latest matching step record."""
        task_id = "0"
        legacy_path = os.path.join(self.log_file_dir, self.log_file_name)
        legacy = self._read_json_or_default(legacy_path, default={})
        traj = legacy.get(task_id, {}).get("traj", [])
        for entry in reversed(traj):
            if entry.get("step") == step:
                entry["tool_error"] = error
                break
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False, indent=4)

        self._append_canonical_event(
            {
                "type": "tool_error",
                "schema_version": "1.0.0",
                "step": step,
                "error": error,
            }
        )

    def log_score(self, score: float, reason: str = "Unknown reason"):
        with open(os.path.join(self.log_file_dir, self.score_file_name), "w") as f:
            f.write(f"score: {score}\nreason: {reason}")
        score_event = normalize_score_event(
            task_name=os.path.basename(self.log_file_dir),
            run_id=f"{os.path.basename(self.log_file_dir)}-0",
            score=score,
            reason=reason,
        )
        self._append_canonical_event(score_event.model_dump())

        # reset tools after logging score
        self.tools = None

    def log_token_usage(self, token_usage: dict[str, int]) -> None:
        """Log token usage to traj.json."""
        with open(os.path.join(self.log_file_dir, self.log_file_name)) as f:
            log_data = json.load(f)

        log_data["token_usage"] = token_usage

        with open(os.path.join(self.log_file_dir, self.log_file_name), "w") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=4)
        _, meta_path = self._canonical_paths()
        meta_data = self._read_json_or_default(meta_path, default={})
        meta_data["token_usage"] = token_usage
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_data, f, ensure_ascii=False, indent=4)

    def reset_traj(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Backup screenshots dir
        screenshots_path = os.path.join(self.log_file_dir, self.screenshots_dir)
        if os.path.exists(screenshots_path):
            os.rename(screenshots_path, f"{screenshots_path}_backup_{timestamp}")

        # Backup marked_screenshots dir
        marked_path = os.path.join(self.log_file_dir, self.marked_screenshots_dir)
        if os.path.exists(marked_path):
            os.rename(marked_path, f"{marked_path}_backup_{timestamp}")

        # Backup traj.json
        traj_path = os.path.join(self.log_file_dir, self.log_file_name)
        if os.path.exists(traj_path):
            backup_traj_path = os.path.join(self.log_file_dir, f"traj_backup_{timestamp}.json")
            os.rename(traj_path, backup_traj_path)
        canonical_path = os.path.join(self.log_file_dir, self.canonical_log_file_name)
        if os.path.exists(canonical_path):
            backup_canonical_path = os.path.join(
                self.log_file_dir, f"traj_canonical_backup_{timestamp}.jsonl"
            )
            os.rename(canonical_path, backup_canonical_path)
        meta_path = os.path.join(self.log_file_dir, self.canonical_meta_file_name)
        if os.path.exists(meta_path):
            backup_meta_path = os.path.join(self.log_file_dir, f"traj_meta_backup_{timestamp}.json")
            os.rename(meta_path, backup_meta_path)

        # Recreate directories and empty traj.json
        os.makedirs(screenshots_path, exist_ok=True)
        os.makedirs(marked_path, exist_ok=True)
        with open(traj_path, "w") as f:
            json.dump({}, f)
        with open(canonical_path, "w", encoding="utf-8") as f:
            f.write("")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({}, f)

        self.tools = None
        logger.info(f"Trajectory reset with backup timestamp: {timestamp}")
