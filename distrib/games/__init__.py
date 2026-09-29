from distrib.config import load as _load_config
from distrib.games.frlg import FrlgAdapter
from distrib.games.swsh import SwshAdapter

ADAPTERS = {
    "swsh": SwshAdapter(),
    "frlg": FrlgAdapter(_load_config().state_dir / "rodizio_pid.json"),
}
