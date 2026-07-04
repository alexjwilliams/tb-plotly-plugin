from setuptools import find_packages, setup

setup(
    name="tb-plotly-plugin",
    version="0.0.1",
    packages=find_packages(),
    install_requires=[
        "tensorboard",
        "werkzeug",
        "plotly",
    ],
    entry_points={
        "tensorboard_plugins": [
            "plotly = tb_plotly_plugin.plugin:PlotlyPlugin",
        ],
    },
)
