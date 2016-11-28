/* Translation maps */

var partyToCandidate = {
  'dem': 'Hillary Clinton',
  'gop': 'Donald Trump',
  'grn': "Jill Stein",
  'lib': 'Gary Johnson',
  'una': 'Evan McMullin',
  'oth': 'Other'
}

var numberToLetter = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

var letterToNumber = {};
for (let i=0; i<numberToLetter.length; ++i) {
  letterToNumber[numberToLetter[i]] = i;
}
var countyToState = {}

var STATE_ABBREVS = [
  'AL', 'AK',
  'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
  'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI',
  'WY'];

var stateToNumber = {};
for (let i=0; i<STATE_ABBREVS.length; ++i) {
  stateToNumber[STATE_ABBREVS[i]] = i;
}


/* Global state variables */
var currentMode = 'pickup';
var countyMode = 'show';
var showStateColors = true;
var stateTotals = {}

/* Data: Read once and store */
var us = null;


var switchModeButton = d3.select('#switchModeButton').html('Move');
var switchModeFunction = function() {
  if (currentMode === 'pickup') {
    switchModeButton.html('Cancel move').classed('btn-danger', false).classed('btn-warning', true);
    currentMode = 'dropoff';
  } else {
    switchModeButton.html('Move').classed('btn-danger', true).classed('btn-warning', false);
    currentMode = 'pickup';
  }
}
switchModeButton.on('click', switchModeFunction);

var countyModeButton = d3.select("#countyModeButton").html("Hide Counties");
var countyModeFunction = function () {
  if (countyMode === 'show') {
    countyMode = 'hide';
    countyModeButton.html("Outlines Only");
    d3.selectAll("path").remove();
    update();
  } else if (countyMode === 'hide' && showStateColors) {
    showStateColors = false;
    countyModeButton.html("Show Counties");
    d3.selectAll("path").remove();
    update();
  } else {
    countyMode = 'show';
    showStateColors = true;
    countyModeButton.html("Hide Counties");
    d3.selectAll("path").remove();
    update();
  }
}
countyModeButton.on('click', countyModeFunction);

var width = 960;
    height = 500;

var path = d3.geo.path();

/* County detail tooltip */
var tooltip = d3.select('body').append('div')
            .attr('class', 'hidden tooltip');

var tooltipInner = tooltip.append('div').attr('class', 'tooltip-inner');
var tooltipTitle = tooltipInner.append('div').attr('class', 'tooltip-title');
var tooltipTable = tooltipInner.append('div').attr('class', 'tooltip-content').append('table').attr('class', 'table county-results');
var tooltipTr = tooltipTable.append('thead').append('tr')
tooltipTr.append('th').html('Candidate');
tooltipTr.append('th').html('Votes');
tooltipTr.append('th').html('Pct.');
var tooltipTbody = tooltipTable.append('tbody');

var svg = d3.select("#states-svg")
            .attr('width', '100%')
            .attr('viewBox', '0 0 ' + width + ' ' + height);

/* On update, compute the number of electors a state would get.
 * Uses 2010 Census data and the algorithm described here:
 * https://en.wikipedia.org/wiki/United_States_congressional_apportionment#The_method_of_equal_proportions
 *
 * @updates stateTotals
 */
var computeElectors = function() {
  let priorities = [];
  let allocated = 153;
  for (let state of STATE_ABBREVS) {
    stateTotals[state].electors = 3;
    if (state !== 'DC' && state !== 'AK') {
      priorities.push({key: state, val: stateTotals[state].population / Math.sqrt(2)});
    }
  }
  priorities.sort(function(a, b) {
    if (a.val === b.val) {
      return 0;
    }
    return a.val < b.val ? 1 : -1;
  });
  while (allocated < 538) {
    let nextUp = priorities[0];
    let nextState = stateTotals[nextUp.key];
    nextState.electors += 1;
    allocated += 1;
    nextUp.val = nextState.population / Math.sqrt((nextState.electors - 2) * (nextState.electors - 1));
    priorities.sort(function(a, b) {
      if (a.val === b.val) {
        return 0;
      }
      return a.val < b.val ? 1 : -1;
    });
  }
}

/* Utilities */

/* If obj has prop as a property, return the value. Else return 0. */
var hasOrZero = function(obj, prop) {
  if (obj.hasOwnProperty(prop)) {
    return obj[prop];
  } else {
    return 0;
  }
}

/* Return the integer d with commas at thousands places */
var intWithCommas = function(d) {
  return d.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/* Return a query parameter from a URL */
var getParameterByName = function (name, url) {
  if (!url) {
    url = window.location.href;
  }
  name = name.replace(/[\[\]]/g, "\\$&");
  var regex = new RegExp("[?&]" + name + "(=([^&#]*)|&|#|$)"),
      results = regex.exec(url);
  if (!results) return null;
  if (!results[2]) return '';
  return decodeURIComponent(results[2].replace(/\+/g, " "));
}

var getColorClass = function(d) {
  if (d.properties.hasOwnProperty('state')) {
    let s = stateTotals[d.properties.state];
    if (s.dem > s.gop) {
      let demPercent = Math.floor(d.properties.dem / (d.properties.gop + d.properties.dem) * 20) * 5;
      if (demPercent < 50) {
        demPercent = 'less-than-50';
      }
      return 'dem-' + demPercent;
    } else {
      let demPercent = Math.floor(d.properties.dem / (d.properties.gop + d.properties.dem) * 20) * 5;
      if (demPercent >= 50) {
        demPercent = 'greater-than-50';
      }
      return 'dem-' + demPercent;
    }
  } else {
    return "black";
  }
}

/**** D3 ****/

/* The main D3 update loop */
var update = function() {
  /* Update elector numbers */
  computeElectors();

  /* Details table rendering */
  var tr = d3.select('#states')
    .selectAll("tr")
      .data(STATE_ABBREVS);

  tr.enter().append("tr");
  var td = tr.selectAll("td")
    .data(function (d, i) {
      let state = stateTotals[STATE_ABBREVS[i]];
      return [STATE_ABBREVS[i], state.population, state.electors,
              state.dem, state.gop, state.grn, state.lib, state.una, state.oth];
    });

  td.enter()
    .append("td");

  td.text(function (d, i) { return intWithCommas(d); })
    .attr("class", function(d, i) {
      if (i === 0) {
        return stateTotals[d].dem > stateTotals[d].gop ? "blue-state" : "red-state";
      } else {
        return null;
      }
    });
  td.exit().remove();
  tr.exit().remove();

  /* Draw United States with colors! */
  let mapPath;

  if (countyMode === 'show') {
    // We do a full, county level rendering
    mapPath = svg.selectAll("path.county-path")
     .data(topojson.feature(us, us.objects.counties).features);

    mapPath
      .enter().append("path")
      .attr("d", path)
      .on("click", function(d) {
        if (currentMode === 'pickup') {
          // Select or deselect the county
          let me = d3.select(this);
          if (me.classed('selection-color')) {
            me.classed(getColorClass(d), true);
            me.classed("selection-color", false);
          } else {
            me.classed(getColorClass(d), false);
            me.classed("selection-color", true);
          }
        } else if (currentMode === 'dropoff') {
          // Move the counties into their new state
          let newState = d.properties.state;
          let newStateData = stateTotals[newState];
          d3.selectAll("path.selection-color")
            .each(function(dd) {
              let oldState = dd.properties.state;
              dd.properties.state = newState;
              let oldStateData = stateTotals[oldState];
              for (let key of ['population', 'electors', 'dem', 'gop', 'lib', 'grn', 'una', 'oth']) {
                newStateData[key] += hasOrZero(dd.properties, key);
                oldStateData[key] -= hasOrZero(dd.properties, key);
              }
            });
          update();
          switchModeFunction();
        }
      })
      .on('mousemove', function(d) {
        // Show county level detail
        var mouse = d3.mouse(svg.node()).map(function(d) {
          return parseInt(d);
        });

        tooltip.classed('hidden', false)
          .attr('style', 'left:' + (d3.event.pageX + 15) + 'px; top:' + (d3.event.pageY - 15) + 'px');
      })
      .on('mouseover', function(d) {
        // Initialize the county level detail
        let theHeading = tooltipTitle.selectAll("h2").data([d.properties.name])
        theHeading.enter().append("h2").attr('class', 'tooltip-title-heading');
        theHeading.html(function(dd) { return dd; });
        let thisData = [];
        let total = 0;
        for (let party in partyToCandidate) {
          let partyTotal = hasOrZero(d.properties, party);
          if (partyTotal > 0) {
            thisData.push([partyToCandidate[party], partyTotal]);
            total += partyTotal;
          }
        }
        let theData = tooltipTbody.selectAll("tr")
          .data(thisData);
        theData.enter().append('tr')
        let theRow = theData.selectAll("td").data(function(dd, i) {
          return [dd[0], dd[1], (100 * dd[1] / total).toFixed(2) + '%'];
        });
        theRow.enter().append('td');
        theRow.html(function(elt, i) { return i === 0 ? elt : intWithCommas(elt); })
        theRow.exit().remove();
        theData.exit().remove();
      })
      .on('mouseout', function() {
        // Hide the county level detail
        tooltip.classed('hidden', true);
      });

    // Actually color the map
    mapPath.attr("class", function(d) { return "county-path " + getColorClass(d); });
  }

  // Draw state boundaries
  mapPath = svg.selectAll("path.state-boundary")
    .data(d3.nest()
            .key(function(d) { return d.hasOwnProperty('properties') ? (d.properties.state || 'other') : 'other'; })
            .entries(us.objects.counties.geometries));

  mapPath.enter().append("path")
    .attr("class", "state-boundary state-boundary-filled");

  mapPath.attr("d", function(d) { return path(topojson.merge(us, d.values)); });
  if (countyMode === 'hide' && showStateColors) {
    // If we're hiding the counties, we want to color whole states
    mapPath.attr('class', function (d) {
      if (stateTotals.hasOwnProperty(d.key)) {
        let s = stateTotals[d.key];
        let dem = hasOrZero(s, 'dem');
        let gop = hasOrZero(s, 'gop');
        let demPercent = Math.floor(dem / (dem + gop) * 20) * 5;
        return "state-boundary dem-" + demPercent + '-state';
      } else {
        return 'state-boundary';
      }
    });
  }

  // Recompute the total number of electoral votes
  let demTotal = 0;
  let gopTotal = 0;
  let count = 0;
  for (let state of STATE_ABBREVS) {
    count += 1;
    let s = stateTotals[state];
    if (s.dem > s.gop) {
      demTotal += s.electors;
    } else {
      gopTotal += s.electors;
    }
  }

  // Color and fill in EV bar
  d3.select('.ev-bar').attr('style', 'background: linear-gradient(to right, #179ee0 0%, #179ee0 ' + (demTotal / 538 * 100) + '%, #ff5d40 ' + (demTotal / 538 * 100) + '%, #ff5d40 100%)');
  $(".ev-bar-dem-total").text(demTotal);
  $(".ev-bar-gop-total").text(gopTotal);
}

/* Read data once! */
d3.json("data/us.json", function(error, usData) {
  if (error) throw error;
  us = usData;

  let shareParameter = getParameterByName('share');
  if (shareParameter) {
    us.objects.counties.geometries.sort(function(x, y) {
      if (x.id < y.id) {
        return -1;
      } else if (x.id > y.id) {
        return 1;
      } else {
        return 0;
      }
    });
    for (let i=0; i<shareParameter.length; ++i) {
      let num = letterToNumber[shareParameter[i]];
      let geom = us.objects.counties.geometries[i];
      if (!geom) {
        console.log("problem ", i);
      }
      if (num !== 51 && geom && geom.hasOwnProperty('properties')) {
        geom.properties.state = STATE_ABBREVS[num];
      }
    }
  }

  for (let i=0; i<us.objects.counties.geometries.length; ++i) {
    let county = us.objects.counties.geometries[i];
    if (!county.hasOwnProperty('properties') || !county.properties.hasOwnProperty("state")) {
      // There are a few numbers in the 72000s which appear to be part of nothing in particular.
      continue;
    }
    countyToState[county.id] = county.properties.state;
    let state;
    if (stateTotals.hasOwnProperty(county.properties.state)) {
      state = stateTotals[county.properties.state];
    } else {
      state = {population: 0, electors: 0, color: county.properties.color, dem: 0, gop: 0, grn: 0, lib: 0, una: 0, oth: 0};
      stateTotals[county.properties.state] = state;
    }
    state.population += hasOrZero(county.properties, 'population');
    state.dem += hasOrZero(county.properties, 'dem');
    state.gop += hasOrZero(county.properties, 'gop');
    state.grn += hasOrZero(county.properties, 'grn');
    state.lib += hasOrZero(county.properties, 'lib');
    state.una += hasOrZero(county.properties, 'una');
    state.oth += hasOrZero(county.properties, 'oth');
  }

  update();

});


/**** Sharing ****/

/* Turn map into URL */
var getShareUrl = function() {
  us.objects.counties.geometries.sort(function(x, y) {
    if (x.id < y.id) {
      return -1;
    } else if (x.id > y.id) {
      return 1;
    } else {
      return 0;
    }
  });
  shareUrl = [];
  for (let geom of us.objects.counties.geometries) {
    if (geom.hasOwnProperty('properties')) {
      shareUrl.push(numberToLetter[stateToNumber[geom.properties.state]]);
    } else {
      shareUrl.push(numberToLetter[51]);
    }
  }
  return window.location.origin + window.location.pathname + '?share=' + shareUrl.join('');
}

/* Setup sharing URL in the share box */
var doShare = function() {
  d3.select("#clipboard-target").attr("value", getShareUrl());
}

$("#shareGroup").hide();

$("#shareButton").popover({
  container: 'body',
  content: $("#shareGroup"),
  title: "Copy URL to Share",
  html: true,
  placement: "left",
  trigger: "focus"
}).on('show.bs.popover', function() { doShare(); $("#shareGroup").show(); });

var clipboard = new Clipboard('[data-clipboard-tooltip]');
clipboard.on('success', function(e) {
  e.clearSelection();
  console.info('Action:', e.action);
  console.info('Text:', e.text);
  console.info('Trigger:', e.trigger);
});
