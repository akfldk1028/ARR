import type { GenerateContentResponse } from '@google/genai';

export type ToolContext = {
  map: google.maps.maps3d.Map3DElement | null;
  placesLib: google.maps.PlacesLibrary | null;
  elevationLib: google.maps.ElevationLibrary | null;
  geocoder: google.maps.Geocoder | null;
  padding: [number, number, number, number];
  setHeldGroundedResponse: (response: GenerateContentResponse | undefined) => void;
  setHeldGroundingChunks: (chunks: Array<any> | undefined) => void;
};

export const toolRegistry: Record<string, (args: unknown, context: ToolContext) => Promise<GenerateContentResponse | string> | GenerateContentResponse | string> = {};
