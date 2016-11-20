from contextlib import contextmanager
import csv
import sys
import time

import click
import requests
from lxml.etree import HTML

BASE_URL = 'http://townhall.com/election/2016/president/{state}/county'

STATE_ABBREVS = [
  'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
  'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME',
  'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
  'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
  'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI',
  'WY']


assert len(STATE_ABBREVS) == 51, "There are 50 states + DC"


def grab_page(abbrev):
  """
  Given a state abbreviation (see `STATE_ABBREVS`), return the content of the page
  on townhall.com which contains the county election results for that page. Returns
  `None` if something goes wrong.

  :param str abbrev: A state abbreviation
  :return: An lxml object containing the content of the page we are retrieving
  :rtype: lxml.etree._Element
  """
  url = BASE_URL.format(state=abbrev)
  res = requests.get(url)
  if not res.ok:
    print("There was a problem retrieving", abbrev, file=sys.stderr)
    return None
  return HTML(res.content)


def parse_page(tree):
  # We find the rows of the election results via an XPATH.
  rows = tree.xpath('//div[@id="election-live"]//table[not(contains(@class, "summary"))]/tbody/tr')

  results = []
  current_result = {}
  for row in rows:
    tds = row.xpath('td')
    if len(tds) == 4:
      # This row starts a new set of county results. We need to restart our results
      if current_result:
        results.append(current_result)

      current_result = {}
      current_result['county'], current_result['pct'] = tds[0].xpath('div/text()')
      assert '%' in current_result['pct'], "Something weird in the percentage"

    # The actual results are in the class name (will be DEM, GOP, LIB, GRN, UNA, OTH)
    # NB: UNA is Evan McMullin
    party = tds[-2].xpath('@class')[0].split(' ')[0].lower()
    if party not in ('dem', 'gop', 'lib', 'grn'):
      name = list(tds[-3].itertext())[0].lower()
      if 'jill' in name:
        party = 'grn'
      elif 'evan' in name:
        party = 'una'
      elif 'gary' in name:
        party = 'lib'
      else:
        party = 'oth'

    # Numbers have commas, get rid of them and '-' is just 0
    num = tds[-2].text.replace(',', '')
    num = '0' if num == '-' else num
    total = int(num)
    current_result[party] = total

  results.append(current_result)
  return results


def results_to_csv(results, state):
  """
  Turn the output of the parse_page function into a collection of CSV lines.
  The order of the output is::

    STATE,County,Reporting,dem,rep,lib,grn,una,oth

  Note that `una` is Evan McMullin.
  """
  output = []
  for result in results:
    output.append((
      state,
      result['county'],
      result['pct'],
      result.get('dem', 0),
      result.get('gop', 0),
      result.get('lib', 0),
      result.get('grn', 0),
      result.get('una', 0),
      result.get('oth', 0)
    ))
  return output


@contextmanager
def open_or_stdin(filename):
  """If filename is not None, yield the open file for writing; else yield sys.stdout"""
  if filename:
    with open(filename, 'wt') as f:
      yield f
  else:
    yield sys.stdout


@contextmanager
def progressbar_or_none(filename, iterator):
  """If filename is None, yield a click progressbar; else yield the original iterator"""
  if not filename:
    yield iterator
  else:
    with click.progressbar(iterator) as pbar:
      yield pbar


@click.command()
@click.option('--output', '-o', default=None, type=click.Path(),
              help="Where to store the output of our queries. If None, will write to stdout")
def main(output):
  with open_or_stdin(output) as f:
    writer = csv.writer(f)
    writer.writerow(['state', 'county', 'reporting', 'dem', 'gop', 'lib', 'grn', 'una', 'oth'])
    with progressbar_or_none(output, STATE_ABBREVS) as pbar:
      for abbrev in pbar:
        tree = grab_page(abbrev)
        results = parse_page(tree)
        writer.writerows(results_to_csv(results, abbrev))
        time.sleep(1)  # Don't be mean


if __name__ == '__main__':
  main()
