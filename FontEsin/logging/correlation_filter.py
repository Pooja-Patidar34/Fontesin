import logging
from FontEsin.middleware.correlation_id import get_correlation_id


class CorrelationIdFilter(logging.Filter):

    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True