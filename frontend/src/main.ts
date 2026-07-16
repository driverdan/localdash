import { mount } from "svelte";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/gabarito/700.css";
import "@fontsource/gabarito/800.css";
import "./styles/base.css";
import "./styles/timeseries.css";
import "./styles/news.css";
import "./styles/events.css";
import "./styles/home.css";
import "./styles/theme-dark.css";
import App from "./App.svelte";

const app = mount(App, { target: document.getElementById("app")! });

export default app;
