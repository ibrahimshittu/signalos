import { HttpSignalOSApi } from './http';

const studioApi = new HttpSignalOSApi();

export const getStudioApi = () => studioApi;
