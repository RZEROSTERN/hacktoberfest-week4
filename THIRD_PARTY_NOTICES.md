# Third-party notices

Slothshot bundles the components below. Their licenses apply to the copies
inside the installers.

| Component | Used for | License |
| --- | --- | --- |
| [Electron](https://www.electronjs.org/) | Desktop shell | MIT (plus Chromium's own notices, shipped alongside) |
| [Ollama](https://ollama.com/) | Running the vision model on this computer | MIT |
| [Nuxt](https://nuxt.com/) / [Vue](https://vuejs.org/) | Web app | MIT |
| [FastAPI](https://fastapi.tiangolo.com/) | Local API | MIT |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server | BSD-3-Clause |
| [Pydantic](https://docs.pydantic.dev/) / [SQLModel](https://sqlmodel.tiangolo.com/) | Validation and storage | MIT |
| [Pillow](https://python-pillow.org/) | Reading, hashing and downscaling images | MIT-CMU |
| [psutil](https://github.com/giampaolo/psutil) | Process and memory accounting | BSD-3-Clause |

Model weights are **not** bundled. The first-launch wizard downloads the model
the user chooses, from Ollama's library, and shows its license before the
download starts. That download is the only time Slothshot uses the network.

> The exact versions and the full license texts are collected during the
> cross-platform build (step 9).
