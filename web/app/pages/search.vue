<script setup lang="ts">
const { query, results, searching, run } = useSearch()
</script>

<template>
  <section>
    <h1>Search</h1>
    <p class="muted">
      Searches descriptions and the text found in your screenshots.
    </p>

    <form @submit.prevent="run">
      <input
        v-model="query"
        type="search"
        placeholder="the screenshot with the booking number"
        aria-label="Search your screenshots"
      >
      <button type="submit" :disabled="searching">Search</button>
    </form>

    <p v-if="results && results.count === 0" class="muted">
      Nothing matched “{{ results.query }}”.
    </p>

    <ul v-else-if="results" class="hits">
      <li v-for="hit in results.hits" :key="hit.id">
        <strong>{{ hit.slug ?? 'screenshot' }}</strong>
        <span v-if="hit.category" class="tag">{{ hit.category }}</span>
        <span v-if="hit.in_review" class="tag review">Review</span>
        <p v-if="hit.description" class="muted">{{ hit.description }}</p>
        <p v-if="hit.snippet" class="snippet">{{ hit.snippet }}</p>
        <p v-else-if="hit.sensitive" class="muted small">
          Marked sensitive, so its text was never stored. Turn on indexing of sensitive text
          in settings to search inside it.
        </p>
        <code class="path">{{ hit.path }}</code>
      </li>
    </ul>

    <p class="muted small">
      <NuxtLink to="/">← Back</NuxtLink>
    </p>
  </section>
</template>

<style scoped>
form { display: flex; gap: .5rem; margin: 1rem 0 1.5rem; }
input { flex: 1; padding: .6rem .75rem; border: 1px solid var(--line); border-radius: 8px;
        background: var(--bg); color: var(--fg); font: inherit; }
button { padding: .6rem 1rem; border: 1px solid var(--line); border-radius: 8px;
         background: var(--bg); color: var(--fg); font: inherit; cursor: pointer; }
.hits { list-style: none; padding: 0; }
.hits li { border-top: 1px solid var(--line); padding: 1rem 0; }
.hits p { margin: .25rem 0; }
.tag { font-size: .75rem; border: 1px solid var(--line); border-radius: 999px;
       padding: .1rem .5rem; margin-left: .5rem; color: var(--muted); }
.review { border-style: dashed; }
.snippet { font-size: .9rem; }
.path { font-size: .75rem; color: var(--muted); word-break: break-all; }
.small { font-size: .875rem; }
</style>
