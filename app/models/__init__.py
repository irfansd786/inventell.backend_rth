"""Import order matters for relationship resolution — keep alphabetical."""

from app.models.activity_log import ActivityLog  # noqa: F401
from app.models.alert import Alert  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.dataset_metadata import DatasetMetadata  # noqa: F401
from app.models.forecast import DemandForecast, ForecastMetric  # noqa: F401
from app.models.inventory import Inventory  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.queue_alert import QueueAlert  # noqa: F401
from app.models.recommendation import Recommendation  # noqa: F401
from app.models.risk import Risk  # noqa: F401
from app.models.sale import Sale  # noqa: F401
from app.models.supplier import Supplier  # noqa: F401
from app.models.transfer import Transfer  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.warehouse import Warehouse  # noqa: F401

