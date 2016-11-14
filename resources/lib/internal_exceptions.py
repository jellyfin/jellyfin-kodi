
# this is an internal exception wrapper that is used to raise exceptions
# when you dont want them logged ot the metric logging system
class ExceptionWrapper(Exception):
    pass
