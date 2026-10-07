import {inject, EmptyFileSystem} from 'langium';
import {createDefaultModule, createDefaultSharedModule} from 'langium/lsp';
import {AcpGeneratedModule, AcpGeneratedSharedModule} from './out/module.js';

export function createServices(){
    const shared=inject(createDefaultSharedModule(EmptyFileSystem),AcpGeneratedSharedModule);
    const services=inject(createDefaultModule({shared}),AcpGeneratedModule);
    shared.ServiceRegistry.register(services);
    return services;
}
