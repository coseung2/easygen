import React from 'react'
import { REQUIRED_FIXTURES } from './fixtures'

export function StateFixtures() {
  return <div className="state-fixtures" data-fixture-count={REQUIRED_FIXTURES.length}>{REQUIRED_FIXTURES.map((state) => <section key={state} data-fixture={state}><h2>{state}</h2><p>{state === 'cost-unknown' ? '비용 미확인' : state}</p></section>)}</div>
}
