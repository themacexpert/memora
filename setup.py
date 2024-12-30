from setuptools import setup, find_packages

setup(
    name="memora",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "neo4j",
        "typing-extensions",
        "qdrant-client",
        "openai",
        "together",
        "groq",
    ],
    python_requires=">=3.10",
)
