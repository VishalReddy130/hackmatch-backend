"""
app/models/team.py

Utilities for the 'teams' MongoDB collection.

MongoDB document structure:
{
    "_id": ObjectId,
    "name": str,                  # team display name, max 60 chars
    "description": str,           # what the team is building / looking for
    "created_by": ObjectId,       # user _id of the creator
    "members": [ObjectId],        # list of user _ids (creator is index 0)
    "max_members": int,           # default 6
    "created_at": datetime
}
"""

from datetime import datetime
from bson import ObjectId


def create_team_document(
    name: str,
    description: str,
    created_by: ObjectId,
) -> dict:
    """
    Build a new team dict ready for db["teams"].insert_one().
    The creator is automatically added as the first (and only) member.
    """
    return {
        "name": name.strip(),
        "description": description.strip(),
        "created_by": created_by,
        "members": [created_by],
        "max_members": 6,
        "created_at": datetime.utcnow(),
    }


def serialize_team(team: dict | None) -> dict | None:
    """
    Convert a raw MongoDB team document into a JSON-safe dict.

    What this does:
      - Renames _id → id and converts ObjectId → str
      - Converts created_by ObjectId → str
      - Converts members list of ObjectIds → list of strings
      - Converts created_at datetime → ISO 8601 string
      - Adds computed field: member_count
    """
    if team is None:
        return None

    result = {**team}

    # _id  →  id  (string)
    result["id"] = str(result.pop("_id"))

    # ObjectId fields → strings
    result["created_by"] = str(result["created_by"])
    result["members"] = [str(m) for m in result.get("members", [])]

    # datetime → ISO string
    if isinstance(result.get("created_at"), datetime):
        result["created_at"] = result["created_at"].isoformat()

    # Computed
    result["member_count"] = len(result["members"])

    return result
