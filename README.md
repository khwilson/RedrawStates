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
> node server.js
```

and then point your browser to `localhost:8080/map.html`. Or, if you want, go
[here](khwilson.github.com/maps/map.html) for the latest live version.

## Acknowledgements

I ganked a lot of stuff from the interwebs to make this. Here is a list:
  * Mike Bostock's tutorial on how to make a bubble map underlies a lot of the shape data:
    [link](https://bost.ocks.org/mike/bubble-map/)
  * Townhall.com's election data [by county](http://townhall.com/election/2016/president/)
  * D3 Tooltips from Lee Howorko [here](http://bl.ocks.org/lhoworko/7753a11efc189a936371)
  * Colors for the map from [FiveThirtyEight's](http://www.fivethirtyeight.com)'s election coverage
  * Lines in the middle of divs from [this StackOverflow](http://stackoverflow.com/questions/1179928/how-can-i-put-a-vertical-line-down-the-center-of-a-div)
  * `getParameterByName` function from [this StackOverflow](http://stackoverflow.com/questions/901115/how-can-i-get-query-string-values-in-javascript)
  * The copy-paste examples from [clipboard.js](www.clipboardjs.com) are copied verbatim
  * [Bootstrap](www.getbootstrap.com), [D3](www.d3js.com), and [jQuery](www.jquery.com) are, of course, indispensable

## Contributors

Kevin Wilson (the owner of the repo) is the main contributor. But some others have helped as well.
Notably:
  * @herbiemarkwort contributed the "0 population => 0 electors" computation

## License

GPL v3
