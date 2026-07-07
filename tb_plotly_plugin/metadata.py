from tensorboard.compat.proto import summary_pb2

PLUGIN_NAME = "plotly"

_DATA_CLASS_TENSOR = getattr(
    summary_pb2,
    "DATA_CLASS_TENSOR",
    getattr(summary_pb2.SummaryMetadata, "DATA_CLASS_TENSOR", 2),
)


def create_summary_metadata(display_name=None, description=None):
    return summary_pb2.SummaryMetadata(
        display_name=display_name or "",
        summary_description=description or "",
        data_class=_DATA_CLASS_TENSOR,
        plugin_data=summary_pb2.SummaryMetadata.PluginData(
            plugin_name=PLUGIN_NAME,
            content=b"",
        ),
    )
