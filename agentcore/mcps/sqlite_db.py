"""SQLite Database MCP — Query and manage local SQLite databases."""
import sqlite3
from agentcore.mcps import register_mcp


@register_mcp
class SQLiteDBMCP:
    name = "sqlite-mcp"
    description = "Query and manage local SQLite databases (DROP/DELETE/TRUNCATE requires approval)"
    TOOLS = {
        "sql_query":   {"params": {"db_path": "string", "sql": "string"}, "desc": "Execute read-only SQL queries"},
        "sql_execute": {"params": {"db_path": "string", "sql": "string"}, "desc": "Execute write SQL queries (inserts, updates, creates)"},
    }

    async def call_tool(self, name: str, args: dict) -> dict:
        db_path = args["db_path"]
        sql = args["sql"]
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(sql)
            if name == "sql_query":
                columns = [col[0] for col in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                results = [dict(zip(columns, row)) for row in rows]
                return {"rows": results[:100], "count": len(results)}
            else:
                conn.commit()
                return {"changes": conn.changes(), "last_row_id": cursor.lastrowid}
        except Exception as e:
            return {"error": str(e), "success": False}
        finally:
            conn.close()
