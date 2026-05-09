"""DuckDB SQL analytics tool for data processing.

Provides SQL query capabilities for:
- CSV/Parquet file analytics
- In-memory data processing
- Aggregations and transformations
- Schema discovery and inspection
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.tools.base import ToolBase


class DuckDBTool(ToolBase):
    name = "duckdb"
    description = (
        "Executes SQL queries on local files (CSV, Parquet) using DuckDB. "
        "Supports aggregations, joins, window functions, and schema inspection."
    )
    parameters: dict[str, str] = {
        "query": "SQL query to execute",
        "file": "Path to CSV or Parquet file (optional, creates in-memory DB if not provided)",
        "limit": "Maximum rows to return (default 100)",
    }

    def execute(self, arguments: dict[str, Any]) -> str:
        query = arguments.get("query", "").strip()
        file_path = arguments.get("file", "").strip()
        limit = int(arguments.get("limit", 100))

        if not query:
            return "Error: No query provided."

        try:
            import duckdb
        except ImportError:
            return "Error: DuckDB not installed. Run: pip install duckdb"

        con = duckdb.connect(read_only=False)

        try:
            if file_path:
                path = Path(file_path)
                if not path.exists():
                    return f"Error: File not found: {file_path}"
                ext = path.suffix.lower()
                if ext == ".csv":
                    con.execute(f"CREATE TABLE data AS SELECT * FROM read_csv_auto('{path}')")
                elif ext == ".parquet":
                    con.execute(f"CREATE TABLE data AS SELECT * FROM read_parquet('{path}')")
                else:
                    return f"Error: Unsupported file type: {ext}"

            if "select" in query.lower() and "limit" not in query.lower():
                query = f"{query} LIMIT {limit}"

            result = con.execute(query).fetchall()

            if not result:
                return "Query executed successfully. No rows returned."

            columns = [desc[0] for desc in con.description] if con.description else []

            if columns:
                formatted = [dict(zip(columns, row)) for row in result]
                return json.dumps(formatted, indent=2, default=str)
            else:
                return "\n".join(str(row) for row in result)

        except Exception as exc:
            return f"Query error: {exc}"
        finally:
            con.close()


_duckdb_tool = DuckDBTool()
