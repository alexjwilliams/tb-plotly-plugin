import json

from tensorboard.compat.proto import (
    summary_pb2,
    tensor_pb2,
    tensor_shape_pb2,
    types_pb2,
)

from .metadata import create_summary_metadata


def plotly_summary(tag, figure, display_name=None, description=None):
    """
    Create a TensorBoard Summary containing a Plotly figure JSON payload.

    Parameters
    ----------
    tag:
        TensorBoard tag.
    figure:
        Either a plotly.graph_objects.Figure, a figure dict, or a JSON string.
    """
    if hasattr(figure, "to_json"):
        figure_json = figure.to_json()
    elif isinstance(figure, dict):
        figure_json = json.dumps(figure)
    elif isinstance(figure, str):
        figure_json = figure
    else:
        raise TypeError(
            "figure must be a plotly Figure, a figure dict, or a JSON string"
        )

    tensor = tensor_pb2.TensorProto(
        dtype=types_pb2.DT_STRING,
        tensor_shape=tensor_shape_pb2.TensorShapeProto(),
        string_val=[figure_json.encode("utf-8")],
    )

    metadata = create_summary_metadata(
        display_name=display_name,
        description=description,
    )

    return summary_pb2.Summary(
        value=[
            summary_pb2.Summary.Value(
                tag=tag,
                tensor=tensor,
                metadata=metadata,
            )
        ]
    )


def add_plotly(
    writer, tag, figure, global_step=None, display_name=None, description=None
):
    """
    Log a Plotly figure to TensorBoard using the custom Plotly plugin.

    This uses PyTorch SummaryWriter's underlying FileWriter.
    """
    summary = plotly_summary(
        tag=tag,
        figure=figure,
        display_name=display_name,
        description=description,
    )

    writer._get_file_writer().add_summary(summary, global_step)
