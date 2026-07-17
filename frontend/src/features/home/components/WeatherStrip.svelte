<script lang="ts">
  import { home } from "../state.svelte";

  // Station observations can lag 20-60 min; the "as of" time keeps a stale
  // reading from presenting as live. Seconds-free local time.
  const fmtAsOf = (iso: string): string => {
    try {
      return new Date(iso).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  // EPA AQI category colors (1 Good .. 6 Hazardous): the standardized scale
  // users know from every AQI product, kept verbatim and confined to the chip.
  // Text flips to white on the darker bands for contrast.
  const AQI_COLORS: Record<number, { bg: string; fg: string }> = {
    1: { bg: "#00e400", fg: "#000" },
    2: { bg: "#ffff00", fg: "#000" },
    3: { bg: "#ff7e00", fg: "#000" },
    4: { bg: "#ff0000", fg: "#fff" },
    5: { bg: "#8f3f97", fg: "#fff" },
    6: { bg: "#7e0023", fg: "#fff" },
  };

  // Unknown/null category yields no inline style; the stylesheet's muted
  // fallback colors apply instead.
  const aqiStyle = (category: number | null): string => {
    const colors = category !== null ? AQI_COLORS[category] : undefined;
    return colors ? `background:${colors.bg};color:${colors.fg}` : "";
  };

  const weather = $derived(home.weather);
  const empty = $derived(
    weather !== null &&
      weather.current === null &&
      weather.periods.length === 0 &&
      weather.aqi === null,
  );
</script>

<article class="widget">
  <div class="widget-head">
    <!-- No view-all link: weather has no feature page to link to. -->
    <h2>Weather</h2>
  </div>
  <div class="weather-widget widget-body">
    {#if !home.weatherLoaded}
      <div class="notice">Loading weather…</div>
      <!-- Error shows only with no payload to render: a failed live refetch
         keeps the previous conditions on screen instead of blanking them. -->
    {:else if weather === null || empty}
      <div class="notice error">Could not load weather.</div>
    {:else}
      <!-- One flex row hosts both conditions and the AQI chip, so the chip
           still renders (alone) when no station observation is usable. -->
      {#if weather.current || weather.aqi}
        <div class="current">
          {#if weather.current}
            {#if weather.current.icon}
              <img src={weather.current.icon} alt="" width="36" height="36" />
            {/if}
            <span class="temp">{weather.current.temperature_f}°F</span>
            <span class="conditions">
              <span class="desc">{weather.current.description}</span>
              <span class="meta">
                {#if weather.current.wind_mph !== null}
                  wind {weather.current.wind_direction ?? ""}
                  {weather.current.wind_mph} mph ·
                {/if}
                {#if weather.current.humidity_percent !== null}
                  {weather.current.humidity_percent}% humidity ·
                {/if}
                {#if weather.current.observed_at}
                  as of {fmtAsOf(weather.current.observed_at)}
                {/if}
              </span>
            </span>
          {/if}
          {#if weather.aqi}
            <span
              class="aqi-chip"
              style={aqiStyle(weather.aqi.category)}
              title={weather.aqi.pollutant
                ? `Primary pollutant: ${weather.aqi.pollutant}`
                : null}
            >
              AQI {weather.aqi.value}{weather.aqi.category_name
                ? ` · ${weather.aqi.category_name}`
                : ""}
            </span>
          {/if}
        </div>
      {/if}
      <!-- Period names come from NWS ("Today" becomes "Tonight" through the
           day) — render them verbatim, never a hardcoded label. -->
      {#each weather.periods as period (period.name)}
        <div class="period" title={period.detailed_forecast}>
          <span class="period-name">{period.name}</span>
          <span class="period-detail">
            {period.temperature}°{period.temperature_unit}
            · {period.short_forecast}
            {#if period.precip_percent}
              · {period.precip_percent}% rain
            {/if}
          </span>
        </div>
      {/each}
    {/if}
  </div>
</article>
