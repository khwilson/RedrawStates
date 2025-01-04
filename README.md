# Redrawing the States

This visualization was an attempt by me to:
1. Understand d3 (one day I should really learn it. :) ), and
2. More importantly, to understand just how janky the electoral college is.

Using this visualization, you can move counties to other states. Currently it's a bit
difficult to use, but what I found, basically, is that
* If you move the three westernmost counties of the Florida panhandle to Alabama, Florida flips
  to Clinton,
* If you move the 10 closest counties of the Upper Peninsula of Michigan to Wisconsin, Michigan
  flips to Clinton,
* If you move the three closest counties of California to Arizona, Arizona flips to Clinton,
* If you move Cook County from Illinois to Indiana, Indiana flips to Clinton (and gains 7
  electoral votes), and Illinois flips to Trump (and loses 7 electoral votes),
* If you move Lake County (just above Chicago) to Wisconsin and those 10 counties of the UP to
  Wisconsin, Clinton wins Illinois, Wisconsin, and Michigan,
* If Camden joined Pennsylvania, Clinton wins both Pennsylvania and New Jersey (and no electoral
  votes change hands),

In total, if only 8 counties move (3 from CA -> AZ, Camden -> PA, Lake -> WI, 3
from FL -> AL), Clinton wins 301 to 237.

## Usage

If you want to try to make sense of the current draft product, then just run

```bash
cd public && python3 -m http.server
```

and then point your browser to `localhost:8080/map.html`. Or, if you want, go
[here](https://kevinhayeswilson.com/redraw) for the latest live version.

## Grabbing data

To grab data and structure it for production, you will need to have both `uv` and `node` 12+ installed. After that, you'll need to install dependencies with:

```bash
uv sync
npm install
```

After that, you can create the 2016, 2020, and 2024 data sets by running:

```bash
uv run redraw 2016 public/data/us.json
uv run redraw 2020 public/data/us2020.json
uv run redraw 2024 public/data/us2024.json
```

If you'd like to recreate the 2012, 2008, and 2004 files, you need to grab the
data set at::

    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VOQCHQ

Supposed you saved it as `countypres_2000-2016.csv`. Then you would run the commands:

```bash
uv run redraw mit 2012 countypres_2000-2016.csv public/data/us2012.json
uv run redraw mit 2008 countypres_2000-2016.csv public/data/us2008.json
uv run redraw mit 2004 countypres_2000-2016.csv public/data/us2004.json
```

Unfortunately, at this time, the Census Bureau's API for 1990 SF1 data seems to be
down, and so we cannot create a file for the year 2000. :-/

## Acknowledgements

I ganked a lot of stuff from the interwebs to make this. Here is a list:
  * Mike Bostock's tutorial on how to make a bubble map underlies a lot of the shape data:
    [link](https://bost.ocks.org/mike/bubble-map/)
  * Townhall.com's election data [by county](http://townhall.com/election/2016/president/) was used in the original 2016 tool
  * In 2020 I moved to the New York Times' data for 2020 and 2016
  * Population and income data come from the Census Bureau's decennial SF1 file
  * D3 Tooltips from Lee Howorko [here](http://bl.ocks.org/lhoworko/7753a11efc189a936371)
  * Colors for the map from [FiveThirtyEight's](http://www.fivethirtyeight.com)'s election coverage
  * Lines in the middle of divs from [this StackOverflow](http://stackoverflow.com/questions/1179928/how-can-i-put-a-vertical-line-down-the-center-of-a-div)
  * `getParameterByName` function from [this StackOverflow](http://stackoverflow.com/questions/901115/how-can-i-get-query-string-values-in-javascript)
  * The copy-paste examples from [clipboard.js](www.clipboardjs.com) are copied verbatim
  * [Bootstrap](www.getbootstrap.com), [D3](www.d3js.com), and [jQuery](www.jquery.com) are, of course, indispensable
  * [css-element-queries](https://github.com/marcj/css-element-queries) from @marcj were super useful for zooming in the previous version of this tool
  * [Connecticut county crosswalk](https://github.com/CT-Data-Collaborative/2022-tract-crosswalk) for Connecticut's updated county equivalents in 2022.

## Contributors

Kevin Wilson (the owner of the repo) is the main contributor. But some others have helped as well.
Notably:
  * @herbiemarkwort contributed the "0 population => 0 electors" computation
  * @Euonia contributed the keyboard shortcut for going to "Move" mode

## License

GPL v3
