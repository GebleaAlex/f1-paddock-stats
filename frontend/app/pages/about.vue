<script setup lang="ts">
import type { Meta } from '~/utils/types'

const { data: meta } = await useApi<Meta>('/meta')
usePageMeta({ title: 'About and data', description: 'Where Paddock Stats gets its data, the licences, and how the numbers are calculated.' })
</script>

<template>
  <div>
    <PageHeader title="About and data" sub="A free, open-source and non-commercial site for Formula 1 statistics." />
    <div class="grid-12">
      <Panel class="span-7" title="How the numbers are made">
        <div class="prose">
          <p>
            Everything is calculated from open datasets, rebuilt after each race weekend. Nothing is scraped from
            official sites and no request you make reaches the data providers.
          </p>
          <p>
            <b>Teammate duels.</b> Teammates are drivers of the same constructor in the same race. Whoever qualified
            ahead wins the qualifying duel. A race duel counts only when both drivers were classified, so a broken
            car is not a lost duel. The qualifying gap compares the last session both drivers set a time in (Q3,
            then Q2, then Q1) and is a percentage of the faster time; the median across races is shown, ignoring
            gaps over 5%, which are almost always a problem lap rather than pace.
          </p>
          <p>
            <b>Other points systems.</b> Seasons can be re-scored under any system used since 1950. To compare
            fairly, only Grand Prix results count, every result counts (the dropped-score rules used until 1990 are
            ignored) and sprints are left out.
          </p>
          <p>
            <b>Lap charts and gaps</b> use lap-by-lap times, available from 1996. Gaps are the difference in total
            race time at the end of each lap.
          </p>
          <p>
            <b>Retirement causes</b> are grouped into crash, technical, penalty and other from the reason recorded
            for each retirement.
          </p>
          <p>
            <b>Race pace</b> is corrected for fuel: about 100 kg at the start, burned evenly, each kilogram costing
            0.03 s a lap. Green-flag laps leave out lap 1, in- and out-laps, safety-car laps and laps more than 7%
            slower than the driver's median. Tyre wear is the slope of fuel-corrected lap time against tyre age over a
            stint of at least five such laps.
          </p>
          <p>
            <b>Pit-stop loss</b> is the in-lap plus the out-lap minus two of the driver's typical laps, over green-flag
            stops only. An
            <b>undercut or overcut</b> is two cars running next to each other, within four seconds, one stopping first
            and the other within six laps; the order after both stops decides it. Stops under a safety car are left out.
          </p>
          <p>
            <b>The strategy simulator</b> (2018 onwards) fits a tyre model on each race: lap time, with fuel taken out,
            is the driver's pace plus a tyre offset, wear for every lap the tyres have done and a trend for the track
            getting faster. Only the chosen driver's race changes; a stop costs the race's pit loss, half of it under a
            safety car and nothing under a red flag. Traffic and rivals reacting are not modelled.
          </p>
          <p>
            <b>Safety cars and wet races</b> (2018 onwards) come from the race leader's track status. A safety car
            that only leads the field away after a red flag counts with the red flag; a race is wet when at least 10%
            of all laps were on intermediate or wet tyres.
          </p>
          <p>
            <b>Telemetry</b> (2018 onwards) is each driver's fastest lap of a session, resampled every 10 metres. The
            track map splits the lap into 25 equal sections and colours each by the faster driver. Clipping is the
            distance at full throttle over which the car still slows down. To compare two laps, every point of
            the first is matched to the moment the other car passed the same place, pinned at the sector lines, where
            the official sector times say exactly when each car passed. Each corner runs from up to 200 m before its
            apex to 150 m after it, and the corners and the straights add up to the lap time gap. When a lap's speed
            trace drops out, the laps are matched by position on track and the corners affected are not measured.
          </p>
          <p>
            <b>The race pace ranking</b> uses the median of each driver's fuel-corrected green-flag laps, with the
            middle half of those laps as the bar. Drivers with fewer than five such laps are not ranked.
          </p>
          <p>
            <b>The driver rating</b> fits every teammate duel at once, measuring each season's gaps against that
            season's typical teammate gap, so eras compare fairly. Teammates must have been entered by the same team,
            and the Indianapolis 500 is left out. The bar on each driver is the 90% range of the fit.
          </p>
          <p>
            <b>The car rating</b> splits every qualifying gap to pole into a part for the car, one number per team per
            season, and a part for the driver, one number per career. Drivers who changed teams tie the cars together.
            Each car is shown as a gap to the fastest car of its season.
          </p>
          <p>
            <b>Title chances</b> simulate the rest of the season 20,000 times, each driver scoring in every remaining
            race like they have so far. It treats races as independent, so it is a guide, not a forecast.
          </p>
        </div>
      </Panel>
      <Panel class="span-5" title="Sources and licences">
        <ul class="sources">
          <li v-for="s in meta?.sources ?? []" :key="s.name">
            <a class="link" :href="s.url" rel="noopener"><b>{{ s.name }}</b></a>
            <div class="small ink-2">{{ s.licence }} · version {{ s.version }}</div>
          </li>
        </ul>
        <p class="small ink-2">
          f1db provides results, standings, entrants, cars, engines and circuit layouts. Jolpica-F1 provides lap-by-lap
          times and positions, shared under the same non-commercial licence. From 2018, tyres, sectors, track status,
          race control messages, weather and telemetry come from Formula 1's live timing through the open-source
          <a class="link" href="https://github.com/theOehrly/Fast-F1" rel="noopener">FastF1</a> library. That data has
          no open licence: it is used only to draw charts and is never offered for download.
        </p>
        <p v-if="meta" class="small muted">Database built {{ new Date(meta.built_at).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) }}.</p>
      </Panel>
      <Panel class="span-12" title="Not official">
        <p class="prose">
          Paddock Stats is unofficial and is not associated in any way with the Formula 1 companies. F1, FORMULA ONE,
          FORMULA 1, FIA FORMULA ONE WORLD CHAMPIONSHIP, GRAND PRIX and related marks are trade marks of Formula One
          Licensing B.V. The site uses no logos or official imagery. Team colours are shown only to tell cars apart.
        </p>
      </Panel>
    </div>
  </div>
</template>

<style scoped>
.sources {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
