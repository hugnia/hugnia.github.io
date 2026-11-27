const search = document.querySelector('.study-search');
const query = document.querySelector('#study-query');
const status = document.querySelector('#study-count');
const studies = [...document.querySelectorAll('#publication-list .study')].map((item) => ({
  item,
  text: item.textContent.toLocaleLowerCase(),
}));

function filterStudies() {
  const terms = query.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  let visible = 0;
  for (const study of studies) {
    const matches = terms.every((term) => study.text.includes(term));
    study.item.hidden = !matches;
    visible += Number(matches);
  }
  status.textContent = visible ? `${visible} ${visible === 1 ? 'study' : 'studies'}` : 'No studies match your search.';
}

if (search && studies.length) {
  search.hidden = false;
  query.addEventListener('input', filterStudies);
  filterStudies();
}

const track = document.querySelector('#featured-work');
const controls = document.querySelector('.work-controls');

if (track && controls && track.children.length > 1) {
  const cards = [...track.children];
  const position = controls.querySelector('.work-position');
  const [previous, next] = controls.querySelectorAll('button');

  function getTrackPosition() {
    const step = cards[1].getBoundingClientRect().left - cards[0].getBoundingClientRect().left;
    return {
      step,
      first: Math.round(track.scrollLeft / step),
      visible: Math.max(1, Math.round(track.clientWidth / step)),
    };
  }

  function updateControls() {
    const { first, visible } = getTrackPosition();
    const last = Math.min(cards.length, first + visible);
    const range = visible === 1 ? last : `${first + 1}–${last}`;
    const label = `${range} of ${cards.length}`;
    if (position.textContent !== label) {
      position.textContent = label;
    }
    previous.setAttribute('aria-disabled', String(track.scrollLeft <= 1));
    next.setAttribute('aria-disabled', String(track.scrollLeft + track.clientWidth >= track.scrollWidth - 1));
  }

  for (const button of [previous, next]) {
    button.addEventListener('click', () => {
      if (button.getAttribute('aria-disabled') === 'true') {
        return;
      }
      const { step, first, visible } = getTrackPosition();
      track.scrollTo({ left: step * (first + visible * Number(button.dataset.direction)) });
    });
  }

  controls.hidden = false;
  track.addEventListener('scroll', updateControls, { passive: true });
  new ResizeObserver(updateControls).observe(track);
  updateControls();
}
