"""
Storage Module - Arsenal Module
Filesystem-based run persistence
Copy-paste ready: Just provide results_root path
"""

import json
import asyncio
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timezone
import base64

STRICT_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+-\d{3}$")
LEGACY_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


class RunStorage:
    """Storage manager for experimental runs"""

    def __init__(self, results_root: str) -> None:
        self.results_root = Path(results_root)

    @staticmethod
    def _sanitize_base_name(raw: str) -> str:
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', raw)
        sanitized = re.sub(r'-\d{3}$', '', sanitized)
        return sanitized or "run"

    def _next_run_id(self, base: str) -> str:
        numbers: List[int] = []
        if self.results_root.exists():
            pattern = re.compile(rf'^{re.escape(base)}-(\d{{3}})$')
            for entry in self.results_root.iterdir():
                if entry.suffix != ".json":
                    continue
                match = pattern.match(entry.stem)
                if match:
                    numbers.append(int(match.group(1)))
        next_number = max(numbers) + 1 if numbers else 1
        return f"{base}-{next_number:03d}"

    async def ensure_results_dir(self) -> None:
        """Ensure results directory exists"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.results_root.mkdir(parents=True, exist_ok=True))

    async def generate_run_id(self, model_name: str) -> str:
        """
        Generate unique run ID with sequential numbering
        
        Args:
            model_name: Model identifier
            
        Returns:
            Unique run ID
        """
        await self.ensure_results_dir()
        
        loop = asyncio.get_running_loop()

        # Helper: Atomic directory creation loop
        def _get_next_id():
            # Sanitize model name - strict charset + required -NNN suffix.
            sanitized = self._sanitize_base_name(model_name)
            if not sanitized:
                sanitized = self._sanitize_base_name(base64.urlsafe_b64encode(model_name.encode()).decode()[:10])

            for _ in range(20): # Retry loop
                # Attempt to reserve this ID atomically via File Creation (Flat JSON)
                run_id = self._next_run_id(sanitized)
                run_file = self.results_root / f"{run_id}.json"
                
                try:
                    # Exclusive file creation is strictly atomic on POSIX
                    with open(run_file, 'x') as f:
                        pass # Touch file to reserve name
                    return run_id
                except FileExistsError:
                    continue # ID taken, retry scan
                    
            raise RuntimeError("Failed to generate unique Run ID after multiple attempts")

        return await loop.run_in_executor(None, _get_next_id)

    async def migrate_legacy_run_ids(self) -> Dict[str, str]:
        """
        Migrate legacy run IDs to strict `<base>-NNN` format.

        Returns:
            Mapping of legacy_id -> strict_run_id for migrated records.
        """
        await self.ensure_results_dir()
        loop = asyncio.get_running_loop()

        def _migrate() -> Dict[str, str]:
            migrated: Dict[str, str] = {}
            if not self.results_root.exists():
                return migrated

            for entry in sorted(self.results_root.iterdir(), key=lambda p: p.name):
                source_path: Path
                source_id: str
                source_data: Dict[str, Any]

                try:
                    if entry.is_file() and entry.suffix == ".json":
                        source_path = entry
                        source_id = entry.stem
                    elif entry.is_dir():
                        candidate = entry / "run.json"
                        if not candidate.exists():
                            continue
                        source_path = candidate
                        source_id = entry.name
                    else:
                        continue

                    if STRICT_RUN_ID_PATTERN.fullmatch(source_id):
                        continue
                    if not LEGACY_RUN_ID_PATTERN.fullmatch(source_id):
                        continue

                    with open(source_path, "r", encoding="utf-8") as f:
                        source_data = json.load(f)
                    if not isinstance(source_data, dict):
                        continue

                    base = self._sanitize_base_name(source_id)
                    strict_id = self._next_run_id(base)
                    strict_path = self.results_root / f"{strict_id}.json"
                    if strict_path.exists():
                        continue

                    source_data["runId"] = strict_id
                    with open(strict_path, "w", encoding="utf-8") as f:
                        json.dump(source_data, f, indent=2)

                    migrated[source_id] = strict_id
                except Exception:
                    continue

            return migrated

        return await loop.run_in_executor(None, _migrate)

    async def save_run(self, run_id: str, run_data: Dict[str, Any]) -> None:
        """
        Save run data to filesystem (flat file preference)

        Args:
            run_id: Unique run identifier
            run_data: Complete run data
        """
        await self.ensure_results_dir()
        
        loop = asyncio.get_running_loop()
        
        # Determine target file (Flat file only)
        # Legacy folders are no longer supported for new writes (migration required)
        run_file = self.results_root / f"{run_id}.json"

        def _write():
            with open(run_file, 'w') as f:
                json.dump(run_data, f, indent=2)
                
        await loop.run_in_executor(None, _write)

    async def list_runs(self) -> List[Dict[str, Any]]:
        """
        List all runs (metadata only) - Supports legacy folders and flat files

        Returns:
            Array of run metadata
        """
        loop = asyncio.get_running_loop()
        
        def _list():
            if not self.results_root.exists():
                return []

            runs_by_id: Dict[str, Dict[str, Any]] = {}
            for entry in self.results_root.iterdir():
                try:
                    run_data = None
                    
                    # Check for legacy folder structure
                    if entry.is_dir():
                        run_json_path = entry / "run.json"
                        if run_json_path.exists():
                            with open(run_json_path, 'r') as f:
                                data = json.load(f)
                                # Basic validation
                                if "runId" in data or "timestamp" in data:
                                    run_data = data
                                
                    # Check for flat file structure
                    elif entry.is_file() and entry.suffix == ".json":
                        with open(entry, 'r') as f:
                            data = json.load(f)
                            if "runId" in data or "timestamp" in data:
                                run_data = data
                    
                    if run_data:
                        run_id = run_data.get("runId", entry.stem)
                        if not isinstance(run_id, str):
                            continue
                        if not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
                            continue

                        metadata = {
                            "runId": run_id,
                            "timestamp": run_data.get("timestamp", ""),
                            "modelName": run_data.get("modelName", "Unknown"),
                            "paradoxId": run_data.get("paradoxId", "Unknown"),
                            "iterationCount": run_data.get("iterationCount", 0),
                            "filePath": f"results/{entry.name}"
                        }
                        current = runs_by_id.get(run_id)
                        if current is None:
                            runs_by_id[run_id] = metadata
                        else:
                            # Prefer strict flat-file entry when duplicates are present.
                            preferred_name = f"{run_id}.json"
                            if entry.name == preferred_name:
                                runs_by_id[run_id] = metadata

                except Exception as e:
                    # Log error but continue listing other files
                    import logging
                    logging.getLogger(__name__).error(f"Error reading run file {entry}: {e}")

            # Helper for robust timestamp parsing
            def parse_ts(ts):
                # Sentinel: earliest possible time, strictly UTC-aware to match stored runs
                sentinel = datetime.min.replace(tzinfo=timezone.utc)
                if not ts: return sentinel

                # Handle 'Z' -> '+00:00'
                ts = ts.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(ts)
                    # If naive, force to UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except ValueError:
                    return sentinel

            # Sort by timestamp, newest first
            runs = list(runs_by_id.values())
            runs.sort(key=lambda x: parse_ts(x.get("timestamp", "")), reverse=True)
            return runs

        return await loop.run_in_executor(None, _list)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """
        Get specific run by ID

        Args:
            run_id: Run identifier

        Returns:
            Complete run data
        """
        if not isinstance(run_id, str) or not STRICT_RUN_ID_PATTERN.fullmatch(run_id):
            raise ValueError("Invalid run_id")
        
        # Path resolution validation
        try:
             run_path = (self.results_root / run_id).resolve()
             root_path = self.results_root.resolve()
             if not str(run_path).startswith(str(root_path)):
                 raise ValueError("Path traversal attempt")
        except Exception:
             raise ValueError("Invalid run_id path")
             
        loop = asyncio.get_running_loop()
        
        def _read():
            # Try flat file first
            flat_path = self.results_root / f"{run_id}.json"
            if flat_path.exists():
                 with open(flat_path, 'r') as f:
                    return json.load(f)
            
            # Fallback to legacy folder
            legacy_path = self.results_root / run_id / "run.json"
            if legacy_path.exists():
                with open(legacy_path, 'r') as f:
                    return json.load(f)
                    
            raise FileNotFoundError(f"Run {run_id} not found")

        return await loop.run_in_executor(None, _read)

    async def update_run(self, run_id: str, updates: Dict[str, Any]) -> None:
        """
        Update existing run (e.g., adding insights)

        Args:
            run_id: Run identifier
            updates: Partial data to merge
        """
        loop = asyncio.get_running_loop()
        
        def _update():
            # Determine path (Flat file only)
            flat_path = self.results_root / f"{run_id}.json"
            
            target_path = flat_path
                
            if target_path.exists():
                with open(target_path, 'r') as f:
                    run_record = json.load(f)
            else:
                run_record = {}

            run_record.update(updates)

            with open(target_path, 'w') as f:
                json.dump(run_record, f, indent=2)

        await loop.run_in_executor(None, _update)
