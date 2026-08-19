/** Convert Tibia's authoritative z coordinate to TibiaHub's display floor. */
export const displayFloor = (internalFloor: number): number => 7 - internalFloor;

export const formatDisplayFloor = (internalFloor: number): string => {
  const value = displayFloor(internalFloor);
  return value > 0 ? `+${value}` : String(value);
};
