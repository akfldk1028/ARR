import React from 'react';

declare module '@vis.gl/react-google-maps' {
  export function useMapsLibrary(name: 'maps3d'): google.maps.Maps3DLibrary | null;
  export function useMapsLibrary(name: 'elevation'): google.maps.ElevationLibrary | null;
  export function useMapsLibrary(name: 'places'): google.maps.PlacesLibrary | null;
  export function useMapsLibrary(name: 'geocoding'): google.maps.GeocodingLibrary | null;
}

declare global {
  namespace google.maps {
    interface Maps3DLibrary {
      Marker3DInteractiveElement?: { new (options: unknown): HTMLElement };
    }

    namespace maps3d {
      interface CameraOptions {
        center?: google.maps.LatLngAltitudeLiteral | null;
        heading?: number | null;
        range?: number | null;
        roll?: number | null;
        tilt?: number | null;
      }

      interface FlyAroundAnimationOptions {
        camera: CameraOptions;
        durationMillis?: number;
        rounds?: number;
      }

      interface FlyToAnimationOptions {
        endCamera: CameraOptions;
        durationMillis?: number;
      }

      interface Map3DElement extends HTMLElement {
        mode?: 'HYBRID' | 'SATELLITE';
        flyCameraAround?: (options: FlyAroundAnimationOptions) => void;
        flyCameraTo?: (options: FlyToAnimationOptions) => void;
        center?: google.maps.LatLngAltitudeLiteral | null;
        heading?: number | null;
        range?: number | null;
        roll?: number | null;
        tilt?: number | null;
        defaultUIHidden?: boolean;
      }

      interface Map3DElementOptions {
        center?: google.maps.LatLngAltitudeLiteral | null;
        heading?: number | null;
        range?: number | null;
        roll?: number | null;
        tilt?: number | null;
        defaultUIHidden?: boolean;
      }
    }
  }
}

export {};
