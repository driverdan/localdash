import { mount } from "svelte";
import "./styles/base.css";
import "./styles/timeseries.css";
import "./styles/news.css";
import "./styles/events.css";
import "./styles/theme-dark.css";
import App from "./App.svelte";

const app = mount(App, { target: document.getElementById("app")! });

export default app;
