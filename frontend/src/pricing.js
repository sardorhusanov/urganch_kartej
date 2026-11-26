import places from './places.json' with { type: 'json' };
export { places };

export function quote(car, start, end) {
  const rate = car.routeRates?.find(rate => rate.from === start.name && rate.to === end.name);
  if (!rate) return null;
  const total = rate.amount;
  const deposit = Math.round(total / 5);
  return {total, deposit, remainder: total - deposit};
}

export const money = n => new Intl.NumberFormat('uz-UZ').format(n);
